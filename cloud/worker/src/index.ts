import { consumeAgentQueue, handleAgent } from "./agent";
import { handleAuth } from "./auth";
import { handleChat } from "./chat";
import { cleanupExpiredFiles, handleFiles } from "./files";
import { handleImages } from "./images";
import { handleLearning } from "./learning";
import { handleAdmin } from "./admin";
import { cleanupBackups, createBackup, handleBackups } from "./backups";
import { handleBridge, markOfflineDevices } from "./bridge";
import { handleMemory } from "./memory";
import { consumeMusicQueue, handleMusic } from "./music";
import { handleNotifications } from "./notifications";
import { handleOAuth } from "./oauth";
import { handleRealtime } from "./realtime";
import { handleWorkspaces } from "./workspaces";
import { currentUser, epochSeconds, errorJson, json, sameOrigin, secure } from "./security";
import type { AgentQueueMessage, Env, RequestContext } from "./types";

const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

async function status(env: Env): Promise<Response> {
  const count = await env.DB.prepare("SELECT COUNT(*) AS count FROM users").first<{ count: number }>();
  return json({
    service: "MyCodexAI Cloud",
    ready: true,
    bootstrap_required: Number(count?.count || 0) === 0,
    agent_configured: Boolean(env.GITHUB_OWNER && env.GITHUB_REPO && !env.GITHUB_OWNER.startsWith("REPLACE_") && !env.GITHUB_REPO.startsWith("REPLACE_")),
    model: env.CHAT_AI_MODEL || env.AI_MODEL || "@cf/meta/llama-3.1-8b-instruct-fp8",
    agent_model: env.AGENT_AI_MODEL || env.AI_MODEL || "@cf/google/gemma-4-26b-a4b-it",
  });
}

async function route(request: Request, env: Env, execution: ExecutionContext): Promise<Response> {
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/{2,}/g, "/");
  if (path.startsWith("/api/") && UNSAFE.has(request.method) && !path.startsWith("/api/internal/") && !sameOrigin(request)) {
    return errorJson("คำขอนี้ไม่ได้มาจากเว็บไซต์ MyCodexAI", 403);
  }
  if (path === "/api/cloud/status" && request.method === "GET") return status(env);
  if (path === "/api/health" && request.method === "GET") return json({ status: "ok", runtime: "cloudflare-workers" });

  const context: RequestContext = { request, env, execution, user: await currentUser(request, env) };
  const handlers = [
    handleOAuth, handleAuth, handleRealtime, handleChat, handleWorkspaces, handleMemory, handleAgent,
    handleFiles, handleImages, handleLearning, handleNotifications, handleBackups, handleBridge, handleAdmin, handleMusic,
  ];
  for (const handler of handlers) {
    const response = await handler(context, path);
    if (response) return response;
  }
  if (path.startsWith("/api/")) return errorJson("ไม่พบ API ที่เรียก", 404);

  if (path === "/" || path === "/index.html") {
    const target = new URL(context.user ? "/index.html" : "/login.html", url);
    return env.ASSETS.fetch(new Request(target, request));
  }
  if (path === "/login" || path === "/login.html") {
    if (context.user) return Response.redirect(new URL("/", url).toString(), 302);
    return env.ASSETS.fetch(new Request(new URL("/login.html", url), request));
  }
  return env.ASSETS.fetch(request);
}

export default {
  async fetch(request: Request, env: Env, execution: ExecutionContext): Promise<Response> {
    try {
      return secure(await route(request, env, execution));
    } catch (error) {
      const detail = error instanceof Error && error.message ? error.message : "ระบบคลาวด์ขัดข้องชั่วคราว";
      return secure(errorJson(detail, detail.includes("ใหญ่เกิน") ? 413 : 400));
    }
  },
  async queue(batch: MessageBatch<AgentQueueMessage>, env: Env): Promise<void> {
    if (batch.messages[0]?.body?.kind === "music") await consumeMusicQueue(batch, env);
    else await consumeAgentQueue(batch, env);
  },
  async scheduled(_controller: ScheduledController, env: Env, _execution: ExecutionContext): Promise<void> {
    const now = epochSeconds();
    await env.DB.batch([
      env.DB.prepare("DELETE FROM sessions WHERE expires_at <= ?").bind(now),
      env.DB.prepare("DELETE FROM invites WHERE expires_at <= ?").bind(now),
      env.DB.prepare("DELETE FROM login_limits WHERE blocked_until < ? AND window_started_at < ?").bind(now - 86_400, now - 86_400),
      env.DB.prepare("DELETE FROM oauth_states WHERE expires_at <= ?").bind(now),
      env.DB.prepare("DELETE FROM oauth_mfa_challenges WHERE expires_at <= ?").bind(now),
      env.DB.prepare("DELETE FROM audit_events WHERE created_at < ?").bind(now - 90 * 86_400),
    ]);
    await cleanupExpiredFiles(env);
    await cleanupBackups(env);
    await markOfflineDevices(env);
    try { await createBackup(env, null); } catch { /* Keep scheduled maintenance healthy when backup storage is unavailable. */ }
  },
};

export { UserEventHub } from "./realtime";
