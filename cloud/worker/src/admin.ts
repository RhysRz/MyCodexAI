import type { RequestContext } from "./types";
import { epochSeconds, errorJson, json } from "./security";

function adminOnly(context: RequestContext): Response | null {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  if (context.user.role !== "admin") return errorJson("เมนูนี้ใช้ได้เฉพาะผู้ดูแลระบบ", 403);
  return null;
}

async function overview(context: RequestContext): Promise<Response> {
  const denied = adminOnly(context);
  if (denied) return denied;
  const now = epochSeconds();
  const counts = await context.env.DB.prepare(
    `SELECT
      (SELECT COUNT(*) FROM users WHERE disabled_at IS NULL) AS users,
      (SELECT COUNT(*) FROM conversations) AS conversations,
      (SELECT COUNT(*) FROM messages) AS messages,
      (SELECT COUNT(*) FROM agent_runs) AS agent_runs,
      (SELECT COUNT(*) FROM agent_runs WHERE status IN ('queued', 'dispatched', 'running')) AS active_runs,
      (SELECT COUNT(*) FROM cloud_files WHERE expires_at > ?) AS files,
      (SELECT COUNT(*) FROM audit_events WHERE kind = 'image_generation' AND outcome = 'ok' AND created_at >= ?) AS images_today,
      (SELECT COUNT(*) FROM training_examples) AS training_examples,
      (SELECT COUNT(*) FROM training_evaluations) AS training_evaluations,
      (SELECT COUNT(*) FROM music_jobs) AS music_jobs`,
  ).bind(now, now - 86_400).first<Record<string, number>>();
  return json({
    counts: counts || {},
    capabilities: [
      { id: "chat", label: "แชทภาษาไทยแบบสตรีม", state: "cloud-native" },
      { id: "agent", label: "Cloud Agent และ Pull Request", state: "cloud-native" },
      { id: "files", label: "ไฟล์แนบชั่วคราว", state: "cloud-native" },
      { id: "images", label: "Image Studio", state: "cloud-native" },
      { id: "training", label: "Training Lab", state: "cloud-native" },
      {
        id: "oauth",
        label: "Social Login (Google / GitHub)",
        state: (context.env.OAUTH_GOOGLE_CLIENT_ID && context.env.OAUTH_GOOGLE_CLIENT_SECRET)
          || (context.env.OAUTH_GITHUB_CLIENT_ID && context.env.OAUTH_GITHUB_CLIENT_SECRET)
          ? "cloud-native" : "configuration-required",
      },
      { id: "music", label: "Music Lab สำหรับ PDF, TAB และ WAV", state: "cloud-runner" },
      { id: "scanned_omr", label: "OMR สำหรับ PDF สแกน", state: "cloud-runner" },
      { id: "terminal", label: "Safe Terminal และ Docker sandbox", state: "remote-worker-required" },
      { id: "ollama", label: "Ollama บนเครื่อง", state: "remote-worker-required" },
    ],
    remote_worker: { connected: false, status: "ยังไม่ได้เชื่อมตัวประมวลผลบนคอม" },
  });
}

async function auditEvents(context: RequestContext): Promise<Response> {
  const denied = adminOnly(context);
  if (denied) return denied;
  const url = new URL(context.request.url);
  const limit = Math.min(100, Math.max(1, Number.parseInt(url.searchParams.get("limit") || "50", 10) || 50));
  const rows = await context.env.DB.prepare(
    `SELECT audit_events.id, audit_events.kind, audit_events.outcome, audit_events.detail,
            audit_events.created_at, users.username
       FROM audit_events LEFT JOIN users ON users.id = audit_events.user_id
      ORDER BY audit_events.created_at DESC LIMIT ?`,
  ).bind(limit).all<{ id: string; kind: string; outcome: string; detail: string; created_at: number; username: string | null }>();
  return json({ events: rows.results || [] });
}

export async function handleAdmin(context: RequestContext, path: string): Promise<Response | null> {
  if (path === "/api/admin/overview" && context.request.method === "GET") return overview(context);
  if (path === "/api/admin/audit" && context.request.method === "GET") return auditEvents(context);
  return null;
}
