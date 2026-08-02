import type { RequestContext } from "./types";
import { audit, epochSeconds, errorJson, json, readJson } from "./security";

interface WorkspacePayload {
  name?: string;
  repository?: string;
  default_branch?: string;
  instructions?: string;
}

function cleanName(value: unknown): string {
  const name = String(value || "MyCodexAI").normalize("NFKC").trim();
  if (!name || name.length > 80) throw new Error("ชื่อ Workspace ต้องมี 1-80 ตัวอักษร");
  return name;
}

function cleanBranch(value: unknown): string {
  const branch = String(value || "main").trim();
  if (!/^[A-Za-z0-9._/-]{1,100}$/.test(branch) || branch.includes("..") || branch.startsWith("/") || branch.endsWith("/")) {
    throw new Error("ชื่อ branch ไม่ถูกต้อง");
  }
  return branch;
}

function configuredRepository(context: RequestContext): string {
  return `${context.env.GITHUB_OWNER}/${context.env.GITHUB_REPO}`;
}

async function ensureDefault(context: RequestContext): Promise<void> {
  if (!context.user) return;
  const existing = await context.env.DB.prepare("SELECT id FROM cloud_workspaces WHERE user_id = ? LIMIT 1")
    .bind(context.user.id).first();
  if (existing) return;
  const now = epochSeconds();
  await context.env.DB.prepare(
    `INSERT INTO cloud_workspaces (id, user_id, name, repository, default_branch, instructions, created_at, updated_at)
     VALUES (?, ?, 'MyCodexAI', ?, 'main', '', ?, ?)`,
  ).bind(crypto.randomUUID(), context.user.id, configuredRepository(context), now, now).run();
}

async function list(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  await ensureDefault(context);
  const rows = await context.env.DB.prepare(
    "SELECT id, name, repository, default_branch, instructions, created_at, updated_at FROM cloud_workspaces WHERE user_id = ? ORDER BY updated_at DESC",
  ).bind(context.user.id).all();
  return json({ workspaces: rows.results || [], allowed_repository: configuredRepository(context) });
}

async function create(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const payload = await readJson<WorkspacePayload>(context.request, 40_000);
  const repository = String(payload.repository || configuredRepository(context)).trim();
  if (repository.toLocaleLowerCase() !== configuredRepository(context).toLocaleLowerCase()) {
    return errorJson("บัญชีนี้อนุญาตให้ Agent ทำงานเฉพาะ repository ที่เชื่อมไว้", 403);
  }
  const now = epochSeconds();
  const id = crypto.randomUUID();
  await context.env.DB.prepare(
    `INSERT INTO cloud_workspaces (id, user_id, name, repository, default_branch, instructions, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
  ).bind(
    id, context.user.id, cleanName(payload.name), repository, cleanBranch(payload.default_branch),
    String(payload.instructions || "").trim().slice(0, 20_000), now, now,
  ).run();
  await audit(context.env, context.user.id, "workspace_created", "ok", `workspace=${id}`);
  return json({ id }, 201);
}

async function remove(context: RequestContext, id: string): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const count = await context.env.DB.prepare("SELECT COUNT(*) AS count FROM cloud_workspaces WHERE user_id = ?")
    .bind(context.user.id).first<{ count: number }>();
  if (Number(count?.count || 0) <= 1) return errorJson("ต้องเหลือ Workspace อย่างน้อยหนึ่งรายการ", 409);
  await context.env.DB.prepare("DELETE FROM cloud_workspaces WHERE id = ? AND user_id = ?").bind(id, context.user.id).run();
  return json({ status: "ok" });
}

export async function handleWorkspaces(context: RequestContext, path: string): Promise<Response | null> {
  if (path === "/api/workspaces" && context.request.method === "GET") return list(context);
  if (path === "/api/workspaces" && context.request.method === "POST") return create(context);
  const item = path.match(/^\/api\/workspaces\/([a-f0-9-]+)$/i);
  if (item && context.request.method === "DELETE") return remove(context, item[1]);
  return null;
}
