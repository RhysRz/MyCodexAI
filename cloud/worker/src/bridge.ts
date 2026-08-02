import type { RequestContext } from "./types";
import { audit, epochSeconds, errorJson, json, randomToken, readJson, sha256 } from "./security";
import { notifyUser } from "./notifications";

const JOB_KINDS = new Set(["health", "agent", "index", "agent_control"]);
const JOB_STATUSES = new Set(["completed", "failed", "cancelled", "awaiting_approval", "needs_input"]);

function parseObject(value: string | null): Record<string, unknown> {
  if (!value) return {};
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" ? parsed as Record<string, unknown> : {};
  } catch {
    return {};
  }
}

function parseList(value: string | null): unknown[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function boundedResult(value: unknown): string {
  const serialized = JSON.stringify(value ?? {});
  if (serialized.length <= 100_000) return serialized;
  const result = value && typeof value === "object" ? value as Record<string, unknown> : {};
  return JSON.stringify({
    run_id: result.run_id,
    status: result.status,
    answer: String(result.answer || "").slice(0, 12_000),
    detail: "รายละเอียดผลลัพธ์ยาวเกินขนาดจัดเก็บบนคลาวด์ กรุณาตรวจงานฉบับเต็มที่คอม",
  });
}

function bearer(request: Request): string {
  const value = request.headers.get("Authorization") || "";
  return value.startsWith("Bearer ") ? value.slice(7) : "";
}

async function bridgeDevice(context: RequestContext): Promise<{ id: string; user_id: string } | null> {
  const token = bearer(context.request);
  if (!token) return null;
  return context.env.DB.prepare(
    "SELECT id, user_id FROM hybrid_devices WHERE token_hash = ? AND revoked_at IS NULL",
  ).bind(await sha256(token)).first<{ id: string; user_id: string }>();
}

async function list(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const rows = await context.env.DB.prepare(
    `SELECT id, name, capabilities_json, status, last_seen_at, created_at
       FROM hybrid_devices WHERE user_id = ? AND revoked_at IS NULL ORDER BY created_at DESC`,
  ).bind(context.user.id).all<{ id: string; name: string; capabilities_json: string; status: string; last_seen_at: number | null; created_at: number }>();
  return json({ devices: (rows.results || []).map((row) => ({ ...row, capabilities: parseList(row.capabilities_json) })) });
}

async function listJobs(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const rows = await context.env.DB.prepare(
    `SELECT j.id, j.device_id, j.kind, j.payload_json, j.status, j.result_json, j.created_at, j.updated_at,
            d.name AS device_name
       FROM hybrid_jobs j JOIN hybrid_devices d ON d.id = j.device_id
      WHERE j.user_id = ? ORDER BY j.created_at DESC LIMIT 30`,
  ).bind(context.user.id).all<{
    id: string; device_id: string; kind: string; payload_json: string; status: string;
    result_json: string | null; created_at: number; updated_at: number; device_name: string;
  }>();
  return json({ jobs: (rows.results || []).map((row) => ({
    ...row,
    payload: parseObject(row.payload_json),
    result: row.result_json ? parseObject(row.result_json) : null,
  })) });
}

async function register(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const payload = await readJson<{ name?: string }>(context.request, 8_000);
  const name = String(payload.name || "MyCodexAI PC").normalize("NFKC").trim().slice(0, 100) || "MyCodexAI PC";
  const id = crypto.randomUUID();
  const token = randomToken(40);
  const now = epochSeconds();
  await context.env.DB.prepare(
    `INSERT INTO hybrid_devices (id, user_id, name, token_hash, capabilities_json, status, created_at)
     VALUES (?, ?, ?, ?, '["health","agent","index","agent_control"]', 'offline', ?)`,
  ).bind(id, context.user.id, name, await sha256(token), now).run();
  await audit(context.env, context.user.id, "bridge_registered", "ok", `device=${id}`);
  return json({ id, name, token, warning: "โทเคนนี้แสดงครั้งเดียว กรุณาเก็บใน Windows Credential Manager หรือ environment variable" }, 201);
}

async function revoke(context: RequestContext, id: string): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  await context.env.DB.prepare("UPDATE hybrid_devices SET revoked_at = ?, status = 'revoked' WHERE id = ? AND user_id = ?")
    .bind(epochSeconds(), id, context.user.id).run();
  return json({ status: "ok" });
}

async function createJob(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const payload = await readJson<{ device_id?: string; kind?: string; payload?: unknown; confirmed?: boolean }>(context.request, 80_000);
  const kind = String(payload.kind || "");
  if (!JOB_KINDS.has(kind)) return errorJson("ชนิดงาน Remote ไม่ถูกต้อง", 400);
  if (payload.confirmed !== true) return errorJson("ต้องยืนยันงานก่อนส่งไปยังคอม", 409);
  if (kind === "agent_control") {
    const control = payload.payload && typeof payload.payload === "object" ? payload.payload as Record<string, unknown> : {};
    if (!new Set(["approve", "reject", "cancel"]).has(String(control.action || ""))) return errorJson("คำสั่งควบคุม Agent ไม่ถูกต้อง", 400);
    if (!/^[a-f0-9-]{36}$/i.test(String(control.run_id || ""))) return errorJson("ไม่พบ Local Agent run ที่ต้องการควบคุม", 400);
  }
  const device = await context.env.DB.prepare(
    "SELECT id FROM hybrid_devices WHERE id = ? AND user_id = ? AND revoked_at IS NULL",
  ).bind(String(payload.device_id || ""), context.user.id).first();
  if (!device) return errorJson("ไม่พบคอมที่เชื่อมไว้", 404);
  const id = crypto.randomUUID();
  const now = epochSeconds();
  await context.env.DB.prepare(
    `INSERT INTO hybrid_jobs (id, user_id, device_id, kind, payload_json, status, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, 'queued', ?, ?)`,
  ).bind(id, context.user.id, String(payload.device_id), kind, JSON.stringify(payload.payload ?? {}), now, now).run();
  return json({ id, status: "queued" }, 202);
}

async function poll(context: RequestContext): Promise<Response> {
  const device = await bridgeDevice(context);
  if (!device) return errorJson("Bridge token ไม่ถูกต้อง", 401);
  const now = epochSeconds();
  await context.env.DB.prepare("UPDATE hybrid_devices SET status = 'online', last_seen_at = ? WHERE id = ?")
    .bind(now, device.id).run();
  const job = await context.env.DB.prepare(
    `SELECT id, kind, payload_json FROM hybrid_jobs
      WHERE device_id = ? AND status = 'queued' ORDER BY created_at ASC LIMIT 1`,
  ).bind(device.id).first<{ id: string; kind: string; payload_json: string }>();
  if (!job) return json({ job: null, poll_after_seconds: 8 });
  await context.env.DB.prepare("UPDATE hybrid_jobs SET status = 'claimed', updated_at = ? WHERE id = ? AND status = 'queued'")
    .bind(now, job.id).run();
  return json({ job: { id: job.id, kind: job.kind, payload: JSON.parse(job.payload_json || "{}") }, poll_after_seconds: 1 });
}

async function report(context: RequestContext): Promise<Response> {
  const device = await bridgeDevice(context);
  if (!device) return errorJson("Bridge token ไม่ถูกต้อง", 401);
  const payload = await readJson<{ job_id?: string; status?: string; result?: unknown }>(context.request, 120_000);
  const status = JOB_STATUSES.has(String(payload.status)) ? String(payload.status) : "failed";
  const now = epochSeconds();
  const job = await context.env.DB.prepare("SELECT user_id, kind, payload_json FROM hybrid_jobs WHERE id = ? AND device_id = ?")
    .bind(String(payload.job_id || ""), device.id).first<{ user_id: string; kind: string; payload_json: string }>();
  if (!job) return errorJson("ไม่พบงาน Remote", 404);
  const completedAt = new Set(["completed", "failed", "cancelled"]).has(status) ? now : null;
  const resultJson = boundedResult(payload.result);
  await context.env.DB.prepare(
    "UPDATE hybrid_jobs SET status = ?, result_json = ?, updated_at = ?, completed_at = ? WHERE id = ? AND device_id = ?",
  ).bind(status, resultJson, now, completedAt, String(payload.job_id), device.id).run();
  if (job.kind === "agent_control") {
    const control = parseObject(job.payload_json) as { parent_job_id?: string };
    if (control.parent_job_id) {
      await context.env.DB.prepare(
        "UPDATE hybrid_jobs SET status = ?, result_json = ?, updated_at = ?, completed_at = ? WHERE id = ? AND user_id = ?",
      ).bind(status, resultJson, now, completedAt, control.parent_job_id, job.user_id).run();
    }
  }
  await notifyUser(context.env, job.user_id, {
    type: "bridge_job",
    title: status === "completed" ? "งานบนคอมเสร็จแล้ว" : status === "awaiting_approval" ? "งานบนคอมรอการอนุมัติ" : status === "needs_input" ? "งานบนคอมต้องการข้อมูลเพิ่ม" : "งานบนคอมไม่สำเร็จ",
    detail: `Remote job ${String(payload.job_id).slice(0, 8)} · ${status}`, resource_id: String(payload.job_id), status,
  });
  return json({ status: "ok" });
}

export async function handleBridge(context: RequestContext, path: string): Promise<Response | null> {
  if (path === "/api/bridge/devices" && context.request.method === "GET") return list(context);
  if (path === "/api/bridge/devices" && context.request.method === "POST") return register(context);
  if (path === "/api/bridge/jobs" && context.request.method === "GET") return listJobs(context);
  if (path === "/api/bridge/jobs" && context.request.method === "POST") return createJob(context);
  const device = path.match(/^\/api\/bridge\/devices\/([a-f0-9-]+)$/i);
  if (device && context.request.method === "DELETE") return revoke(context, device[1]);
  if (path === "/api/internal/bridge/poll" && context.request.method === "GET") return poll(context);
  if (path === "/api/internal/bridge/report" && context.request.method === "POST") return report(context);
  return null;
}

export async function markOfflineDevices(context: RequestContext["env"]): Promise<void> {
  await context.DB.prepare(
    "UPDATE hybrid_devices SET status = 'offline' WHERE revoked_at IS NULL AND last_seen_at IS NOT NULL AND last_seen_at < ?",
  ).bind(epochSeconds() - 90).run();
}
