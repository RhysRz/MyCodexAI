import type { RequestContext } from "./types";
import { audit, epochSeconds, errorJson, json, readJson, safeEqual, secure } from "./security";

interface MusicPayload {
  file_id?: string;
}

interface MusicCallbackPayload {
  job_id?: string;
  status?: string;
  analysis?: unknown;
  artifacts?: Array<{ kind?: string; file_name?: string; media_type?: string; contents_base64?: string }>;
  error_detail?: string;
}

interface MusicJobRow {
  id: string;
  user_id: string;
  file_id: string;
  file_name: string;
  status: string;
  analysis_json: string | null;
  error_detail: string | null;
  created_at: number;
  updated_at: number;
  completed_at: number | null;
}

const ALLOWED_SUFFIXES = [".pdf", ".wav", ".wave"];
const CALLBACK_STATUSES = new Set(["running", "completed", "failed"]);
const ARTIFACTS = new Set(["analysis", "midi", "chords", "tab"]);
const USER_DAILY_LIMIT = 3;

function bearer(request: Request): string {
  const authorization = request.headers.get("Authorization") || "";
  return authorization.startsWith("Bearer ") ? authorization.slice(7) : "";
}

async function runnerAuthorized(context: RequestContext): Promise<boolean> {
  return Boolean(context.env.RUNNER_CALLBACK_SECRET) && safeEqual(bearer(context.request), context.env.RUNNER_CALLBACK_SECRET);
}

function parseJson(value: string | null): unknown {
  if (!value) return null;
  try { return JSON.parse(value) as unknown; } catch { return null; }
}

async function artifactsFor(context: RequestContext, jobId: string): Promise<Array<Record<string, string>>> {
  const rows = await context.env.DB.prepare(
    "SELECT kind, file_name, media_type FROM music_artifacts WHERE job_id = ? ORDER BY kind",
  ).bind(jobId).all<{ kind: string; file_name: string; media_type: string }>();
  return (rows.results || []).map((item) => ({
    ...item,
    url: `/api/music/jobs/${jobId}/artifacts/${item.kind}`,
  }));
}

async function publicJob(context: RequestContext, row: MusicJobRow): Promise<Record<string, unknown>> {
  return {
    job_id: row.id,
    file_id: row.file_id,
    file_name: row.file_name,
    status: row.status,
    analysis: parseJson(row.analysis_json),
    error_detail: row.error_detail,
    created_at: row.created_at,
    updated_at: row.updated_at,
    completed_at: row.completed_at,
    artifacts: await artifactsFor(context, row.id),
  };
}

async function ownedJob(context: RequestContext, id: string): Promise<MusicJobRow | null> {
  if (!context.user) return null;
  return context.env.DB.prepare("SELECT * FROM music_jobs WHERE id = ? AND user_id = ?").bind(id, context.user.id).first<MusicJobRow>();
}

async function listJobs(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const rows = await context.env.DB.prepare(
    "SELECT * FROM music_jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT 30",
  ).bind(context.user.id).all<MusicJobRow>();
  const jobs = [];
  for (const row of rows.results || []) jobs.push(await publicJob(context, row));
  return json({
    jobs,
    processing: "github-runner",
    supported: ["PDF โน้ตแบบมีข้อความหรือเวกเตอร์", "PDF กีตาร์/Bass TAB ทั้งเวกเตอร์และภาพสแกน", "PDF โน้ตสแกนผ่าน Audiveris OMR", "WAV"],
    scanned_omr: true,
  });
}

async function dispatchJob(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const payload = await readJson<MusicPayload>(context.request, 8_000);
  const fileId = String(payload.file_id || "").trim();
  const file = await context.env.DB.prepare(
    "SELECT id, name, size_bytes, status FROM cloud_files WHERE id = ? AND user_id = ? AND expires_at > ?",
  ).bind(fileId, context.user.id, epochSeconds()).first<{ id: string; name: string; size_bytes: number; status: string }>();
  if (!file || file.status !== "ready") return errorJson("ไม่พบไฟล์ที่พร้อมประมวลผล", 404);
  if (!ALLOWED_SUFFIXES.some((suffix) => file.name.toLocaleLowerCase().endsWith(suffix))) {
    return errorJson("Music Lab บน Cloud รองรับ PDF และ WAV", 400);
  }
  if (context.user.role !== "admin") {
    const now = epochSeconds();
    const count = await context.env.DB.prepare(
      "SELECT COUNT(*) AS count FROM music_jobs WHERE user_id = ? AND created_at >= ?",
    ).bind(context.user.id, now - (now % 86_400)).first<{ count: number }>();
    if (Number(count?.count || 0) >= USER_DAILY_LIMIT) return errorJson("ใช้สิทธิ์ Music Lab ครบแล้วสำหรับวันนี้", 429);
  }
  if (!context.env.GITHUB_TOKEN || !context.env.GITHUB_OWNER || !context.env.GITHUB_REPO) {
    return errorJson("ยังไม่ได้เชื่อม GitHub Runner", 503);
  }
  const id = crypto.randomUUID();
  const now = epochSeconds();
  await context.env.DB.prepare(
    "INSERT INTO music_jobs (id, user_id, file_id, file_name, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'dispatching', ?, ?)",
  ).bind(id, context.user.id, file.id, file.name.slice(0, 240), now, now).run();
  const response = await fetch(`https://api.github.com/repos/${encodeURIComponent(context.env.GITHUB_OWNER)}/${encodeURIComponent(context.env.GITHUB_REPO)}/dispatches`, {
    method: "POST",
    headers: {
      "Accept": "application/vnd.github+json",
      "Authorization": `Bearer ${context.env.GITHUB_TOKEN}`,
      "Content-Type": "application/json",
      "User-Agent": "MyCodexAI-Cloud/1.0",
      "X-GitHub-Api-Version": "2026-03-10",
    },
    body: JSON.stringify({ event_type: "mycodexai-music", client_payload: { job_id: id, file_id: file.id, file_name: file.name, user_id: context.user.id } }),
  });
  if (!response.ok) {
    await context.env.DB.prepare(
      "UPDATE music_jobs SET status = 'failed', error_detail = ?, updated_at = ?, completed_at = ? WHERE id = ?",
    ).bind("ส่งงานให้ GitHub Runner ไม่สำเร็จ", now, now, id).run();
    await audit(context.env, context.user.id, "music_dispatched", "failed", `job=${id}; github=${response.status}`);
    return errorJson("ส่งงาน Music Lab ไม่สำเร็จ กรุณาลองใหม่", 503);
  }
  await context.env.DB.prepare("UPDATE music_jobs SET status = 'dispatched', updated_at = ? WHERE id = ?").bind(epochSeconds(), id).run();
  await audit(context.env, context.user.id, "music_dispatched", "ok", `job=${id}; file=${file.id}`);
  const row = await ownedJob(context, id);
  return json(await publicJob(context, row!), 202);
}

function decodeBase64(value: string): ArrayBuffer {
  const binary = atob(value);
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
}

async function callback(context: RequestContext): Promise<Response> {
  if (!(await runnerAuthorized(context))) return errorJson("Runner secret ไม่ถูกต้อง", 401);
  const payload = await readJson<MusicCallbackPayload>(context.request, 4_000_000);
  const id = String(payload.job_id || "");
  const status = String(payload.status || "");
  if (!CALLBACK_STATUSES.has(status)) return errorJson("สถานะ Music job ไม่ถูกต้อง", 400);
  const job = await context.env.DB.prepare("SELECT * FROM music_jobs WHERE id = ?").bind(id).first<MusicJobRow>();
  if (!job) return errorJson("ไม่พบ Music job", 404);
  const artifacts = Array.isArray(payload.artifacts) ? payload.artifacts.slice(0, 8) : [];
  let totalBytes = 0;
  const statements: D1PreparedStatement[] = [];
  for (const item of artifacts) {
    const kind = String(item.kind || "");
    const encoded = String(item.contents_base64 || "");
    if (!ARTIFACTS.has(kind) || !encoded) continue;
    const contents = decodeBase64(encoded);
    totalBytes += contents.byteLength;
    if (contents.byteLength > 1_500_000 || totalBytes > 3_000_000) return errorJson("ผลลัพธ์ Music Lab มีขนาดใหญ่เกินไป", 413);
    statements.push(context.env.DB.prepare(
      "INSERT OR REPLACE INTO music_artifacts (job_id, kind, file_name, media_type, contents) VALUES (?, ?, ?, ?, ?)",
    ).bind(id, kind, String(item.file_name || `${kind}.bin`).slice(0, 160), String(item.media_type || "application/octet-stream").slice(0, 100), contents));
  }
  if (statements.length) await context.env.DB.batch(statements);
  const now = epochSeconds();
  await context.env.DB.prepare(
    "UPDATE music_jobs SET status = ?, analysis_json = ?, error_detail = ?, updated_at = ?, completed_at = ? WHERE id = ?",
  ).bind(
    status,
    payload.analysis ? JSON.stringify(payload.analysis).slice(0, 1_000_000) : job.analysis_json,
    String(payload.error_detail || "").slice(0, 3_000) || null,
    now,
    status === "completed" || status === "failed" ? now : null,
    id,
  ).run();
  await audit(context.env, job.user_id, "music_callback", status, `job=${id}; artifacts=${statements.length}`);
  return json({ status: "ok" });
}

async function downloadArtifact(context: RequestContext, jobId: string, kind: string): Promise<Response> {
  const job = await ownedJob(context, jobId);
  if (!job) return errorJson("ไม่พบ Music job", 404);
  const item = await context.env.DB.prepare(
    "SELECT file_name, media_type, contents FROM music_artifacts WHERE job_id = ? AND kind = ?",
  ).bind(jobId, kind).first<{ file_name: string; media_type: string; contents: ArrayBuffer }>();
  if (!item) return errorJson("ไม่พบไฟล์ผลลัพธ์", 404);
  return secure(new Response(item.contents, { headers: {
    "Content-Type": item.media_type,
    "Content-Disposition": `attachment; filename="${item.file_name.replace(/[^A-Za-z0-9._-]/g, "_")}"`,
    "Cache-Control": "private, no-store",
  } }));
}

export async function handleMusic(context: RequestContext, path: string): Promise<Response | null> {
  if (path === "/api/music/jobs" && context.request.method === "GET") return listJobs(context);
  if (path === "/api/music/jobs" && context.request.method === "POST") return dispatchJob(context);
  if (path === "/api/internal/music/callback" && context.request.method === "POST") return callback(context);
  const match = path.match(/^\/api\/music\/jobs\/([a-f0-9-]+)\/artifacts\/([a-z]+)$/i);
  if (match && context.request.method === "GET") return downloadArtifact(context, match[1], match[2]);
  return null;
}
