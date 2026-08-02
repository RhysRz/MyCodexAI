import type { RequestContext } from "./types";
import { audit, epochSeconds, errorJson, json, readJson, safeEqual } from "./security";

const CHUNK_BYTES = 512 * 1024;
const D1_MAX_FILE_BYTES = 10 * 1024 * 1024;
const R2_MAX_FILE_BYTES = 80 * 1024 * 1024;
const D1_MAX_USER_BYTES = 50 * 1024 * 1024;
const R2_MAX_USER_BYTES = 1024 * 1024 * 1024;
const MAX_CHUNKS = Math.ceil(D1_MAX_FILE_BYTES / CHUNK_BYTES);

interface CloudFileRow {
  id: string;
  user_id: string;
  name: string;
  media_type: string;
  size_bytes: number;
  chunk_count: number;
  status: string;
  created_at: number;
  expires_at: number;
  storage_backend?: string;
  storage_key?: string | null;
}

function safeName(value: unknown): string {
  const name = String(value || "ไฟล์แนบ").normalize("NFKC").replace(/[\u0000-\u001f\u007f\\/]/g, "_").trim();
  return (name || "ไฟล์แนบ").slice(0, 180);
}

function publicFile(row: CloudFileRow): Record<string, unknown> {
  return {
    id: row.id,
    name: row.name,
    media_type: row.media_type,
    size_bytes: Number(row.size_bytes),
    chunk_count: Number(row.chunk_count),
    status: row.status,
    created_at: row.created_at,
    expires_at: row.expires_at,
    storage_backend: row.storage_backend || "d1",
    download_url: row.status === "ready" ? `/api/files/${row.id}` : null,
  };
}

async function ownedFile(context: RequestContext, id: string): Promise<CloudFileRow | null> {
  if (!context.user) return null;
  return context.env.DB.prepare("SELECT * FROM cloud_files WHERE id = ? AND user_id = ?")
    .bind(id, context.user.id).first<CloudFileRow>();
}

async function createUpload(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const payload = await readJson<{ name?: string; media_type?: string; size_bytes?: number }>(context.request, 8_000);
  const size = Math.floor(Number(payload.size_bytes || 0));
  const r2 = Boolean(context.env.OBJECTS);
  const maximumFile = r2 ? R2_MAX_FILE_BYTES : D1_MAX_FILE_BYTES;
  const maximumUser = r2 ? R2_MAX_USER_BYTES : D1_MAX_USER_BYTES;
  if (!Number.isFinite(size) || size < 1 || size > maximumFile) {
    return errorJson(`ไฟล์ต้องมีขนาดไม่เกิน ${Math.floor(maximumFile / 1024 / 1024)} MB`, 413);
  }
  const usage = await context.env.DB.prepare(
    "SELECT COALESCE(SUM(size_bytes), 0) AS total FROM cloud_files WHERE user_id = ? AND expires_at > ?",
  ).bind(context.user.id, epochSeconds()).first<{ total: number }>();
  if (Number(usage?.total || 0) + size > maximumUser) {
    return errorJson(`พื้นที่ไฟล์ของบัญชีครบ ${Math.floor(maximumUser / 1024 / 1024)} MB แล้ว กรุณาลบไฟล์เก่า`, 413);
  }
  const now = epochSeconds();
  const row: CloudFileRow = {
    id: crypto.randomUUID(),
    user_id: context.user.id,
    name: safeName(payload.name),
    media_type: String(payload.media_type || "application/octet-stream").slice(0, 120),
    size_bytes: size,
    chunk_count: Math.ceil(size / CHUNK_BYTES),
    status: "uploading",
    created_at: now,
    expires_at: now + 7 * 86_400,
    storage_backend: r2 ? "r2" : "d1",
    storage_key: r2 ? `users/${context.user.id}/uploads/${crypto.randomUUID()}` : null,
  };
  await context.env.DB.prepare(
    `INSERT INTO cloud_files
      (id, user_id, name, media_type, size_bytes, chunk_count, status, created_at, expires_at, storage_backend, storage_key)
     VALUES (?, ?, ?, ?, ?, ?, 'uploading', ?, ?, ?, ?)`,
  ).bind(
    row.id, row.user_id, row.name, row.media_type, row.size_bytes, r2 ? 1 : row.chunk_count,
    row.created_at, row.expires_at, row.storage_backend, row.storage_key,
  ).run();
  return json({ ...publicFile(row), chunk_bytes: CHUNK_BYTES, direct_upload: r2 }, 201);
}

async function uploadChunk(context: RequestContext, id: string, indexText: string): Promise<Response> {
  const row = await ownedFile(context, id);
  if (!row) return errorJson("ไม่พบไฟล์แนบ", 404);
  if (row.status !== "uploading") return errorJson("ไฟล์นี้อัปโหลดเสร็จแล้ว", 409);
  const index = Number.parseInt(indexText, 10);
  if (!Number.isInteger(index) || index < 0 || index >= row.chunk_count || index >= MAX_CHUNKS) {
    return errorJson("ลำดับชิ้นไฟล์ไม่ถูกต้อง", 400);
  }
  const advertised = Number(context.request.headers.get("Content-Length") || 0);
  if (advertised > CHUNK_BYTES) return errorJson("ชิ้นไฟล์ใหญ่เกิน 512 KB", 413);
  const contents = await context.request.arrayBuffer();
  if (!contents.byteLength || contents.byteLength > CHUNK_BYTES) return errorJson("ขนาดชิ้นไฟล์ไม่ถูกต้อง", 413);
  await context.env.DB.prepare(
    `INSERT INTO cloud_file_chunks (file_id, chunk_index, contents) VALUES (?, ?, ?)
     ON CONFLICT(file_id, chunk_index) DO UPDATE SET contents = excluded.contents`,
  ).bind(id, index, contents).run();
  return json({ status: "ok", chunk_index: index });
}

async function uploadContent(context: RequestContext, id: string): Promise<Response> {
  const row = await ownedFile(context, id);
  if (!row) return errorJson("ไม่พบไฟล์แนบ", 404);
  if (row.status !== "uploading" || row.storage_backend !== "r2" || !row.storage_key || !context.env.OBJECTS) {
    return errorJson("ไฟล์นี้ไม่ได้ใช้การอัปโหลดโดยตรง", 409);
  }
  const advertised = Number(context.request.headers.get("Content-Length") || 0);
  if (advertised && advertised !== row.size_bytes) return errorJson("ขนาดไฟล์ไม่ตรงกับข้อมูลที่ลงทะเบียน", 409);
  await context.env.OBJECTS.put(row.storage_key, context.request.body, {
    httpMetadata: { contentType: row.media_type, contentDisposition: `attachment; filename*=UTF-8''${encodeURIComponent(row.name)}` },
    customMetadata: { owner: row.user_id, file_id: row.id },
  });
  const object = await context.env.OBJECTS.head(row.storage_key);
  if (!object || object.size !== row.size_bytes) {
    await context.env.OBJECTS.delete(row.storage_key);
    return errorJson("ข้อมูลไฟล์ที่อัปโหลดมาไม่ครบ", 409);
  }
  await context.env.DB.prepare("UPDATE cloud_files SET status = 'ready', chunk_count = 1 WHERE id = ? AND user_id = ?")
    .bind(id, context.user!.id).run();
  await audit(context.env, context.user!.id, "cloud_file_uploaded", "ok", `R2 attachment uploaded (${row.size_bytes} bytes)`);
  return json({ ...publicFile({ ...row, status: "ready", chunk_count: 1 }) });
}

async function finishUpload(context: RequestContext, id: string): Promise<Response> {
  const row = await ownedFile(context, id);
  if (!row) return errorJson("ไม่พบไฟล์แนบ", 404);
  const info = await context.env.DB.prepare(
    "SELECT COUNT(*) AS chunks, COALESCE(SUM(length(contents)), 0) AS bytes FROM cloud_file_chunks WHERE file_id = ?",
  ).bind(id).first<{ chunks: number; bytes: number }>();
  if (Number(info?.chunks || 0) !== row.chunk_count || Number(info?.bytes || 0) !== row.size_bytes) {
    return errorJson("ชิ้นไฟล์ยังมาไม่ครบ กรุณาอัปโหลดต่อ", 409);
  }
  await context.env.DB.prepare("UPDATE cloud_files SET status = 'ready' WHERE id = ? AND user_id = ?")
    .bind(id, context.user!.id).run();
  await audit(context.env, context.user!.id, "cloud_file_uploaded", "ok", `Temporary attachment uploaded (${row.size_bytes} bytes)`);
  return json({ ...publicFile({ ...row, status: "ready" }) });
}

async function listFiles(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const rows = await context.env.DB.prepare(
    "SELECT * FROM cloud_files WHERE user_id = ? AND expires_at > ? ORDER BY created_at DESC LIMIT 50",
  ).bind(context.user.id, epochSeconds()).all<CloudFileRow>();
  const maximum = context.env.OBJECTS ? R2_MAX_FILE_BYTES : D1_MAX_FILE_BYTES;
  return json({
    files: (rows.results || []).filter((row) => !row.media_type.startsWith("application/x-mycodexai-")).map(publicFile),
    chunk_bytes: CHUNK_BYTES, max_file_bytes: maximum, storage_backend: context.env.OBJECTS ? "r2" : "d1-fallback",
  });
}

async function deleteFile(context: RequestContext, id: string): Promise<Response> {
  const row = await ownedFile(context, id);
  if (!row) return errorJson("ไม่พบไฟล์แนบ", 404);
  if (row.storage_backend === "r2" && row.storage_key && context.env.OBJECTS) await context.env.OBJECTS.delete(row.storage_key);
  await context.env.DB.prepare("DELETE FROM cloud_files WHERE id = ? AND user_id = ?").bind(id, context.user!.id).run();
  await audit(context.env, context.user!.id, "cloud_file_deleted", "ok", "Temporary attachment deleted");
  return json({ status: "ok" });
}

function bearer(request: Request): string {
  const value = request.headers.get("Authorization") || "";
  return value.startsWith("Bearer ") ? value.slice(7) : "";
}

async function runnerDownload(context: RequestContext, id: string): Promise<Response> {
  if (!context.env.RUNNER_CALLBACK_SECRET || !(await safeEqual(bearer(context.request), context.env.RUNNER_CALLBACK_SECRET))) {
    return errorJson("Runner authentication failed", 401);
  }
  const row = await context.env.DB.prepare("SELECT * FROM cloud_files WHERE id = ? AND status = 'ready' AND expires_at > ?")
    .bind(id, epochSeconds()).first<CloudFileRow>();
  if (!row) return errorJson("Attachment not found", 404);
  return fileResponse(context, row);
}

async function userDownload(context: RequestContext, id: string): Promise<Response> {
  const row = await ownedFile(context, id);
  if (!row || row.status !== "ready" || row.expires_at <= epochSeconds()) return errorJson("ไม่พบไฟล์แนบ", 404);
  return fileResponse(context, row);
}

async function fileResponse(context: RequestContext, row: CloudFileRow): Promise<Response> {
  if (row.storage_backend === "r2" && row.storage_key && context.env.OBJECTS) {
    const object = await context.env.OBJECTS.get(row.storage_key);
    if (!object) return errorJson("Attachment not found", 404);
    return new Response(object.body, { headers: {
      "Content-Type": row.media_type,
      "Content-Disposition": `attachment; filename*=UTF-8''${encodeURIComponent(row.name)}`,
      "Cache-Control": "private, no-store",
      "X-MyCodexAI-File-Name": encodeURIComponent(row.name),
    } });
  }
  const chunks = await context.env.DB.prepare(
    "SELECT chunk_index, contents FROM cloud_file_chunks WHERE file_id = ? ORDER BY chunk_index ASC",
  ).bind(row.id).all<{ chunk_index: number; contents: ArrayBuffer }>();
  const body = new Uint8Array(row.size_bytes);
  let offset = 0;
  for (const chunk of chunks.results || []) {
    const bytes = new Uint8Array(chunk.contents);
    body.set(bytes, offset);
    offset += bytes.byteLength;
  }
  if (offset !== row.size_bytes) return errorJson("Attachment is incomplete", 409);
  return new Response(body, {
    headers: {
      "Content-Type": row.media_type,
      "Content-Disposition": `attachment; filename*=UTF-8''${encodeURIComponent(row.name)}`,
      "Cache-Control": "private, no-store",
      "X-MyCodexAI-File-Name": encodeURIComponent(row.name),
    },
  });
}

export async function handleFiles(context: RequestContext, path: string): Promise<Response | null> {
  if (path === "/api/files" && context.request.method === "POST") return createUpload(context);
  if (path === "/api/files" && context.request.method === "GET") return listFiles(context);
  const chunk = path.match(/^\/api\/files\/([a-f0-9-]+)\/chunks\/(\d+)$/i);
  if (chunk && context.request.method === "PUT") return uploadChunk(context, chunk[1], chunk[2]);
  const finish = path.match(/^\/api\/files\/([a-f0-9-]+)\/finish$/i);
  if (finish && context.request.method === "POST") return finishUpload(context, finish[1]);
  const content = path.match(/^\/api\/files\/([a-f0-9-]+)\/content$/i);
  if (content && context.request.method === "PUT") return uploadContent(context, content[1]);
  const item = path.match(/^\/api\/files\/([a-f0-9-]+)$/i);
  if (item && context.request.method === "GET") return userDownload(context, item[1]);
  if (item && context.request.method === "DELETE") return deleteFile(context, item[1]);
  const internal = path.match(/^\/api\/internal\/files\/([a-f0-9-]+)$/i);
  if (internal && context.request.method === "GET") return runnerDownload(context, internal[1]);
  return null;
}

export async function cleanupExpiredFiles(env: RequestContext["env"]): Promise<void> {
  if (env.OBJECTS) {
    const rows = await env.DB.prepare("SELECT storage_key FROM cloud_files WHERE expires_at <= ? AND storage_backend = 'r2' AND storage_key IS NOT NULL")
      .bind(epochSeconds()).all<{ storage_key: string }>();
    for (const row of rows.results || []) await env.OBJECTS.delete(row.storage_key);
  }
  await env.DB.prepare("DELETE FROM cloud_files WHERE expires_at <= ?").bind(epochSeconds()).run();
}
