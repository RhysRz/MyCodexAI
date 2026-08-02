import type { Env, RequestContext } from "./types";
import { audit, epochSeconds, errorJson, json } from "./security";

const TABLES = [
  "conversations", "messages", "agent_runs", "cloud_workspaces", "memory_documents",
  "memory_chunks", "music_jobs", "user_notifications", "training_examples", "training_evaluations",
] as const;

async function encryptionKey(env: Env): Promise<CryptoKey> {
  if (!env.AUTH_ENCRYPTION_KEY || env.AUTH_ENCRYPTION_KEY.length < 24) throw new Error("ยังไม่ได้ตั้งค่ากุญแจเข้ารหัส Backup");
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(env.AUTH_ENCRYPTION_KEY));
  return crypto.subtle.importKey("raw", digest, { name: "AES-GCM" }, false, ["encrypt"]);
}

async function collect(env: Env): Promise<{ payload: Record<string, unknown>; records: number }> {
  const data: Record<string, unknown> = {};
  let records = 0;
  for (const table of TABLES) {
    try {
      const rows = await env.DB.prepare(`SELECT * FROM ${table} LIMIT 5000`).all();
      const results = rows.results || [];
      records += results.length;
      data[table] = results;
    } catch {
      data[table] = [];
    }
  }
  const users = await env.DB.prepare(
    "SELECT id, username, role, created_at, disabled_at FROM users LIMIT 1000",
  ).all();
  data.users = users.results || [];
  records += (users.results || []).length;
  return {
    payload: { format: "mycodexai-backup-v1", created_at: epochSeconds(), data },
    records,
  };
}

export async function createBackup(env: Env, createdBy: string | null): Promise<string> {
  const id = crypto.randomUUID();
  const now = epochSeconds();
  await env.DB.prepare(
    `INSERT INTO backup_snapshots (id, created_by, status, created_at, expires_at)
     VALUES (?, ?, 'creating', ?, ?)`,
  ).bind(id, createdBy, now, now + 30 * 86_400).run();
  try {
    const { payload, records } = await collect(env);
    const plain = new TextEncoder().encode(JSON.stringify(payload));
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const cipher = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv }, await encryptionKey(env), plain));
    const archive = new Uint8Array(5 + iv.length + cipher.length);
    archive.set(new TextEncoder().encode("MCB1\n"), 0);
    archive.set(iv, 5);
    archive.set(cipher, 17);
    let storageKey: string | null = null;
    let inline: ArrayBuffer | null = archive.buffer;
    if (env.OBJECTS) {
      storageKey = `backups/${id}.mcb`;
      await env.OBJECTS.put(storageKey, archive, { httpMetadata: { contentType: "application/octet-stream" } });
      inline = null;
    }
    await env.DB.prepare(
      `UPDATE backup_snapshots SET status = 'ready', encrypted_contents = ?, storage_key = ?,
       size_bytes = ?, record_count = ? WHERE id = ?`,
    ).bind(inline, storageKey, archive.byteLength, records, id).run();
  } catch (error) {
    await env.DB.prepare("UPDATE backup_snapshots SET status = 'failed', error_detail = ? WHERE id = ?")
      .bind(error instanceof Error ? error.message.slice(0, 2_000) : "Backup failed", id).run();
    throw error;
  }
  return id;
}

function adminOnly(context: RequestContext): Response | null {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  if (context.user.role !== "admin") return errorJson("เมนูนี้ใช้ได้เฉพาะผู้ดูแลระบบ", 403);
  return null;
}

async function list(context: RequestContext): Promise<Response> {
  const denied = adminOnly(context); if (denied) return denied;
  const rows = await context.env.DB.prepare(
    `SELECT id, status, size_bytes, record_count, created_at, expires_at, error_detail
       FROM backup_snapshots ORDER BY created_at DESC LIMIT 30`,
  ).all();
  return json({ backups: rows.results || [], encrypted: true, retention_days: 30 });
}

async function create(context: RequestContext): Promise<Response> {
  const denied = adminOnly(context); if (denied) return denied;
  const id = await createBackup(context.env, context.user!.id);
  await audit(context.env, context.user!.id, "backup_created", "ok", `backup=${id}`);
  return json({ id, status: "ready" }, 201);
}

async function download(context: RequestContext, id: string): Promise<Response> {
  const denied = adminOnly(context); if (denied) return denied;
  const row = await context.env.DB.prepare(
    "SELECT encrypted_contents, storage_key, status FROM backup_snapshots WHERE id = ?",
  ).bind(id).first<{ encrypted_contents: ArrayBuffer | null; storage_key: string | null; status: string }>();
  if (!row || row.status !== "ready") return errorJson("ไม่พบ Backup ที่พร้อมดาวน์โหลด", 404);
  let body: ArrayBuffer | ReadableStream | null = row.encrypted_contents;
  if (!body && row.storage_key && context.env.OBJECTS) body = (await context.env.OBJECTS.get(row.storage_key))?.body || null;
  if (!body) return errorJson("ไม่พบข้อมูล Backup", 404);
  return new Response(body, { headers: {
    "Content-Type": "application/octet-stream",
    "Content-Disposition": `attachment; filename="mycodexai-backup-${id.slice(0, 8)}.mcb"`,
    "Cache-Control": "private, no-store",
  } });
}

export async function handleBackups(context: RequestContext, path: string): Promise<Response | null> {
  if (path === "/api/admin/backups" && context.request.method === "GET") return list(context);
  if (path === "/api/admin/backups" && context.request.method === "POST") return create(context);
  const item = path.match(/^\/api\/admin\/backups\/([a-f0-9-]+)$/i);
  if (item && context.request.method === "GET") return download(context, item[1]);
  return null;
}

export async function cleanupBackups(env: Env): Promise<void> {
  const rows = await env.DB.prepare("SELECT id, storage_key FROM backup_snapshots WHERE expires_at <= ?")
    .bind(epochSeconds()).all<{ id: string; storage_key: string | null }>();
  if (env.OBJECTS) {
    for (const row of rows.results || []) if (row.storage_key) await env.OBJECTS.delete(row.storage_key);
  }
  await env.DB.prepare("DELETE FROM backup_snapshots WHERE expires_at <= ?").bind(epochSeconds()).run();
}
