import type { Env, RequestContext } from "./types";
import { errorJson, json } from "./security";
import { DurableObject } from "cloudflare:workers";

export interface RealtimeEvent {
  type: string;
  title?: string;
  detail?: string;
  resource_id?: string;
  status?: string;
  progress?: number;
  action_url?: string;
  created_at?: number;
}

export class UserEventHub extends DurableObject<Env> {
  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/connect") {
      if (request.headers.get("Upgrade")?.toLocaleLowerCase() !== "websocket") {
        return new Response("Expected WebSocket", { status: 426 });
      }
      const pair = new WebSocketPair();
      const [client, server] = Object.values(pair);
      this.ctx.acceptWebSocket(server);
      server.serializeAttachment({ connected_at: Date.now() });
      server.send(JSON.stringify({ type: "connected", created_at: Math.floor(Date.now() / 1_000) }));
      return new Response(null, { status: 101, webSocket: client });
    }
    if (url.pathname === "/broadcast" && request.method === "POST") {
      const payload = await request.text();
      for (const socket of this.ctx.getWebSockets()) {
        try { socket.send(payload); } catch { try { socket.close(1011, "delivery failed"); } catch { /* no-op */ } }
      }
      return json({ delivered: this.ctx.getWebSockets().length });
    }
    return new Response("Not found", { status: 404 });
  }

  async webSocketMessage(socket: WebSocket, message: ArrayBuffer | string): Promise<void> {
    if (typeof message === "string" && message === "ping") socket.send("pong");
  }
}

export async function publishEvent(env: Env, userId: string, event: RealtimeEvent): Promise<void> {
  try {
    const id = env.EVENT_HUB.idFromName(userId);
    await env.EVENT_HUB.get(id).fetch("https://event-hub/broadcast", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...event, created_at: event.created_at || Math.floor(Date.now() / 1_000) }),
    });
  } catch {
    // Realtime delivery is best-effort; durable state remains in D1.
  }
}

export async function handleRealtime(context: RequestContext, path: string): Promise<Response | null> {
  if (path === "/api/realtime" && context.request.method === "GET") {
    if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
    if (context.request.headers.get("Upgrade")?.toLocaleLowerCase() !== "websocket") {
      return errorJson("ปลายทางนี้ต้องเชื่อมต่อด้วย WebSocket", 426);
    }
    const stub = context.env.EVENT_HUB.get(context.env.EVENT_HUB.idFromName(context.user.id));
    return stub.fetch(new Request("https://event-hub/connect", context.request));
  }
  return null;
}
