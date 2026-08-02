import type { Env, RequestContext } from "./types";
import { epochSeconds, errorJson, json } from "./security";
import { publishEvent, type RealtimeEvent } from "./realtime";

export async function notifyUser(
  env: Env,
  userId: string,
  event: RealtimeEvent,
  persist = true,
): Promise<void> {
  const now = epochSeconds();
  if (persist) {
    await env.DB.prepare(
      `INSERT INTO user_notifications (id, user_id, kind, title, detail, action_url, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
    ).bind(
      crypto.randomUUID(), userId, event.type.slice(0, 80), String(event.title || "MyCodexAI").slice(0, 180),
      String(event.detail || "").slice(0, 2_000), event.action_url ? String(event.action_url).slice(0, 500) : null, now,
    ).run();
  }
  await publishEvent(env, userId, { ...event, created_at: now });
}

async function list(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const rows = await context.env.DB.prepare(
    `SELECT id, kind, title, detail, action_url, read_at, created_at
       FROM user_notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 50`,
  ).bind(context.user.id).all();
  const unread = await context.env.DB.prepare(
    "SELECT COUNT(*) AS count FROM user_notifications WHERE user_id = ? AND read_at IS NULL",
  ).bind(context.user.id).first<{ count: number }>();
  return json({ notifications: rows.results || [], unread: Number(unread?.count || 0) });
}

async function markRead(context: RequestContext, id?: string): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const now = epochSeconds();
  if (id) {
    await context.env.DB.prepare("UPDATE user_notifications SET read_at = ? WHERE id = ? AND user_id = ?")
      .bind(now, id, context.user.id).run();
  } else {
    await context.env.DB.prepare("UPDATE user_notifications SET read_at = ? WHERE user_id = ? AND read_at IS NULL")
      .bind(now, context.user.id).run();
  }
  return json({ status: "ok" });
}

export async function handleNotifications(context: RequestContext, path: string): Promise<Response | null> {
  if (path === "/api/notifications" && context.request.method === "GET") return list(context);
  if (path === "/api/notifications/read" && context.request.method === "POST") return markRead(context);
  const item = path.match(/^\/api\/notifications\/([a-f0-9-]+)\/read$/i);
  if (item && context.request.method === "POST") return markRead(context, item[1]);
  return null;
}
