import type { Env, RequestContext } from "./types";
import { audit, epochSeconds, errorJson, json, readJson } from "./security";

interface MemoryPayload {
  title?: string;
  content?: string;
  kind?: string;
  workspace_id?: string;
}

interface EmbeddingOutput {
  data?: number[][] | number[];
  shape?: number[];
}

const EMBEDDING_FALLBACK = "@cf/qwen/qwen3-embedding-0.6b";

function splitText(value: string): string[] {
  const text = value.normalize("NFC").trim();
  const chunks: string[] = [];
  let cursor = 0;
  while (cursor < text.length && chunks.length < 60) {
    let end = Math.min(text.length, cursor + 1_600);
    if (end < text.length) {
      const boundary = Math.max(text.lastIndexOf("\n", end), text.lastIndexOf(" ", end));
      if (boundary > cursor + 800) end = boundary;
    }
    chunks.push(text.slice(cursor, end).trim());
    cursor = Math.max(end - 180, cursor + 1);
  }
  return chunks.filter(Boolean);
}

function vectorsFrom(output: unknown): number[][] {
  if (!output || typeof output !== "object") return [];
  const data = (output as EmbeddingOutput).data;
  if (!Array.isArray(data) || !data.length) return [];
  if (Array.isArray(data[0])) return data as number[][];
  return [data as number[]];
}

async function embed(env: Env, texts: string[]): Promise<number[][]> {
  const output = await (env.AI as unknown as { run(model: string, input: unknown): Promise<unknown> }).run(
    env.EMBEDDING_MODEL || EMBEDDING_FALLBACK,
    { text: texts },
  );
  return vectorsFrom(output);
}

async function workspaceOwned(context: RequestContext, workspaceId: string): Promise<boolean> {
  if (!workspaceId || !context.user) return true;
  return Boolean(await context.env.DB.prepare("SELECT id FROM cloud_workspaces WHERE id = ? AND user_id = ?")
    .bind(workspaceId, context.user.id).first());
}

async function create(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const payload = await readJson<MemoryPayload>(context.request, 180_000);
  const content = String(payload.content || "").normalize("NFC").trim();
  if (!content || content.length > 80_000) return errorJson("เนื้อหาความจำต้องมี 1-80,000 ตัวอักษร", 400);
  const workspaceId = String(payload.workspace_id || "").trim();
  if (!(await workspaceOwned(context, workspaceId))) return errorJson("ไม่พบ Workspace", 404);
  const chunks = splitText(content);
  const id = crypto.randomUUID();
  const now = epochSeconds();
  const title = String(payload.title || "บันทึกความรู้").normalize("NFC").trim().slice(0, 180) || "บันทึกความรู้";
  const kind = String(payload.kind || "note").replace(/[^a-z0-9_-]/gi, "").slice(0, 40) || "note";
  await context.env.DB.prepare(
    `INSERT INTO memory_documents
      (id, user_id, workspace_id, title, kind, content_preview, chunk_count, status, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, 'indexing', ?, ?)`,
  ).bind(id, context.user.id, workspaceId || null, title, kind, content.slice(0, 800), chunks.length, now, now).run();

  const vectorIds: string[] = [];
  const statements: D1PreparedStatement[] = [];
  chunks.forEach((chunk, index) => {
    const vectorId = crypto.randomUUID();
    vectorIds.push(vectorId);
    statements.push(context.env.DB.prepare(
      `INSERT INTO memory_chunks (id, document_id, user_id, workspace_id, chunk_index, content, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
    ).bind(vectorId, id, context.user!.id, workspaceId || null, index, chunk, now));
  });
  if (statements.length) await context.env.DB.batch(statements);

  let status = "ready";
  try {
    const vectors = await embed(context.env, chunks);
    if (vectors.length !== chunks.length) throw new Error("embedding count mismatch");
    await context.env.VECTORIZE.upsert(vectors.map((values, index) => ({
      id: vectorIds[index],
      namespace: context.user!.id,
      values,
      metadata: {
        user_id: context.user!.id,
        workspace_id: workspaceId || "global",
        document_id: id,
        kind,
        title,
        chunk_index: index,
      },
    })));
  } catch {
    status = "keyword-ready";
  }
  await context.env.DB.prepare("UPDATE memory_documents SET status = ?, updated_at = ? WHERE id = ?")
    .bind(status, epochSeconds(), id).run();
  await audit(context.env, context.user.id, "memory_indexed", status, `document=${id}; chunks=${chunks.length}`);
  return json({ id, title, chunk_count: chunks.length, status }, 201);
}

async function list(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const rows = await context.env.DB.prepare(
    `SELECT id, workspace_id, title, kind, content_preview, chunk_count, status, created_at, updated_at
       FROM memory_documents WHERE user_id = ? ORDER BY updated_at DESC LIMIT 100`,
  ).bind(context.user.id).all();
  return json({ documents: rows.results || [] });
}

async function remove(context: RequestContext, id: string): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const rows = await context.env.DB.prepare("SELECT id FROM memory_chunks WHERE document_id = ? AND user_id = ?")
    .bind(id, context.user.id).all<{ id: string }>();
  const ids = (rows.results || []).map((item) => item.id);
  if (ids.length) {
    try { await context.env.VECTORIZE.deleteByIds(ids); } catch { /* D1 remains authoritative. */ }
  }
  await context.env.DB.prepare("DELETE FROM memory_documents WHERE id = ? AND user_id = ?").bind(id, context.user.id).run();
  return json({ status: "ok" });
}

async function keywordSearch(env: Env, userId: string, query: string, workspaceId: string, limit: number): Promise<string[]> {
  const terms = query.normalize("NFC").split(/\s+/).map((term) => term.trim()).filter((term) => term.length >= 2).slice(0, 5);
  if (!terms.length) return [];
  const pattern = `%${terms[0].replaceAll("%", "").replaceAll("_", "")}%`;
  const rows = workspaceId
    ? await env.DB.prepare(
      "SELECT content FROM memory_chunks WHERE user_id = ? AND (workspace_id = ? OR workspace_id IS NULL) AND content LIKE ? LIMIT ?",
    ).bind(userId, workspaceId, pattern, limit).all<{ content: string }>()
    : await env.DB.prepare("SELECT content FROM memory_chunks WHERE user_id = ? AND content LIKE ? LIMIT ?")
      .bind(userId, pattern, limit).all<{ content: string }>();
  return (rows.results || []).map((item) => item.content);
}

export async function retrieveMemory(env: Env, userId: string, query: string, workspaceId = "", limit = 5): Promise<string[]> {
  try {
    const [vector] = await embed(env, [query.slice(0, 4_000)]);
    if (!vector) throw new Error("no embedding");
    const result = await env.VECTORIZE.query(vector, {
      topK: Math.min(10, Math.max(1, limit)),
      namespace: userId,
      returnMetadata: "all",
    });
    const ids = (result.matches || []).map((item) => item.id).filter(Boolean);
    if (!ids.length) return keywordSearch(env, userId, query, workspaceId, limit);
    const placeholders = ids.map(() => "?").join(",");
    const rows = await env.DB.prepare(
      `SELECT id, workspace_id, content FROM memory_chunks WHERE user_id = ? AND id IN (${placeholders})`,
    ).bind(userId, ...ids).all<{ id: string; workspace_id: string | null; content: string }>();
    const byId = new Map((rows.results || [])
      .filter((row) => !workspaceId || !row.workspace_id || row.workspace_id === workspaceId)
      .map((row) => [row.id, row.content]));
    return ids.map((id) => byId.get(id)).filter((value): value is string => Boolean(value)).slice(0, limit);
  } catch {
    return keywordSearch(env, userId, query, workspaceId, limit);
  }
}

async function search(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const url = new URL(context.request.url);
  const query = String(url.searchParams.get("q") || "").trim();
  if (!query) return json({ results: [] });
  const results = await retrieveMemory(context.env, context.user.id, query, String(url.searchParams.get("workspace") || ""), 8);
  return json({ results });
}

export async function handleMemory(context: RequestContext, path: string): Promise<Response | null> {
  if (path === "/api/memory/documents" && context.request.method === "GET") return list(context);
  if (path === "/api/memory/documents" && context.request.method === "POST") return create(context);
  if (path === "/api/memory/search" && context.request.method === "GET") return search(context);
  const item = path.match(/^\/api\/memory\/documents\/([a-f0-9-]+)$/i);
  if (item && context.request.method === "DELETE") return remove(context, item[1]);
  return null;
}
