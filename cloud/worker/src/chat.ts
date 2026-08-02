import type { RequestContext } from "./types";
import { audit, epochSeconds, errorJson, json, readJson, secure } from "./security";
import { retrieveMemory } from "./memory";

interface ChatPayload {
  message?: string;
  conversation_id?: string;
  workspace_id?: string;
}

interface ChatMessageRow {
  role: "user" | "assistant";
  content: string;
  created_at: number;
}

const SYSTEM_PROMPT = `คุณคือ MyCodex ผู้ช่วย AI เพศชายของผู้ใช้ พูดและอธิบายภาษาไทยให้ถูกต้อง เป็นธรรมชาติ และอ่านง่าย
ตอบตรงคำถามก่อน แล้วค่อยอธิบายรายละเอียดที่จำเป็น ห้ามแต่งข้อมูลว่าได้ทำงานในเครื่องหรือแก้ไฟล์แล้วหากยังไม่มีผลลัพธ์จาก Agent
เมื่อผู้ใช้ถามเรื่องโค้ด ให้ตอบเหมือนวิศวกรซอฟต์แวร์อาวุโส เน้นความถูกต้อง ความปลอดภัย และขั้นตอนที่นำไปใช้ได้จริง
รักษาบุคลิกสุภาพ เป็นกันเอง และเรียกตัวเองว่า MyCodex`;

function cleanMessage(value: unknown): string {
  const message = String(value || "").trim();
  if (!message || message.length > 8_000) throw new Error("ข้อความต้องมี 1-8,000 ตัวอักษร");
  return message;
}

async function conversationFor(context: RequestContext, requested?: string): Promise<string> {
  if (!context.user) throw new Error("ต้องเข้าสู่ระบบ");
  if (requested) {
    const owned = await context.env.DB.prepare(
      "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
    ).bind(requested, context.user.id).first<{ id: string }>();
    if (owned) return owned.id;
  }
  const latest = await context.env.DB.prepare(
    "SELECT id FROM conversations WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
  ).bind(context.user.id).first<{ id: string }>();
  if (latest) return latest.id;
  const id = crypto.randomUUID();
  const now = epochSeconds();
  await context.env.DB.prepare(
    "INSERT INTO conversations (id, user_id, title, created_at, updated_at) VALUES (?, ?, 'แชทใหม่', ?, ?)",
  ).bind(id, context.user.id, now, now).run();
  return id;
}

async function recentMessages(context: RequestContext, conversationId: string): Promise<ChatMessageRow[]> {
  const rows = await context.env.DB.prepare(
    `SELECT role, content, created_at FROM (
       SELECT role, content, created_at FROM messages
        WHERE conversation_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 24
     ) ORDER BY created_at ASC`,
  ).bind(conversationId, context.user?.id || "").all<ChatMessageRow>();
  return rows.results || [];
}

async function learnedExamples(context: RequestContext): Promise<Array<{ instruction: string; ideal_response: string }>> {
  try {
    const rows = await context.env.DB.prepare(
      "SELECT instruction, ideal_response FROM training_examples ORDER BY created_at DESC LIMIT 8",
    ).all<{ instruction: string; ideal_response: string }>();
    return rows.results || [];
  } catch {
    // Keep chat available while a new migration is still being applied.
    return [];
  }
}

function aiText(output: unknown): string {
  if (typeof output === "string") return output;
  if (!output || typeof output !== "object") return "";
  const record = output as Record<string, unknown>;
  if (typeof record.response === "string") return record.response;
  if (typeof record.output_text === "string") return record.output_text;
  const choices = Array.isArray(record.choices) ? record.choices : [];
  const first = choices[0] as Record<string, unknown> | undefined;
  const message = first?.message as Record<string, unknown> | undefined;
  if (typeof message?.content === "string") return message.content;
  return "";
}

function streamDelta(frame: string): string {
  const data = frame.split("\n").filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trim()).join("");
  if (!data || data === "[DONE]") return "";
  try {
    const parsed = JSON.parse(data) as Record<string, unknown>;
    if (typeof parsed.response === "string") return parsed.response;
    const choices = Array.isArray(parsed.choices) ? parsed.choices : [];
    const first = choices[0] as Record<string, unknown> | undefined;
    const delta = first?.delta as Record<string, unknown> | undefined;
    if (typeof delta?.content === "string") return delta.content;
  } catch {
    return "";
  }
  return "";
}

async function saveAssistant(context: RequestContext, conversationId: string, answer: string): Promise<void> {
  if (!context.user || !answer.trim()) return;
  const now = epochSeconds();
  await context.env.DB.batch([
    context.env.DB.prepare(
      "INSERT INTO messages (id, conversation_id, user_id, role, content, created_at) VALUES (?, ?, ?, 'assistant', ?, ?)",
    ).bind(crypto.randomUUID(), conversationId, context.user.id, answer.trim().slice(0, 40_000), now),
    context.env.DB.prepare("UPDATE conversations SET updated_at = ? WHERE id = ? AND user_id = ?").bind(now, conversationId, context.user.id),
  ]);
}

async function streamChat(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const payload = await readJson<ChatPayload>(context.request, 20_000);
  const message = cleanMessage(payload.message);
  const conversationId = await conversationFor(context, payload.conversation_id);
  const now = epochSeconds();
  const existingCount = await context.env.DB.prepare(
    "SELECT COUNT(*) AS count FROM messages WHERE conversation_id = ?",
  ).bind(conversationId).first<{ count: number }>();
  await context.env.DB.batch([
    context.env.DB.prepare(
      "INSERT INTO messages (id, conversation_id, user_id, role, content, created_at) VALUES (?, ?, ?, 'user', ?, ?)",
    ).bind(crypto.randomUUID(), conversationId, context.user.id, message, now),
    context.env.DB.prepare(
      "UPDATE conversations SET title = CASE WHEN ? = 0 THEN ? ELSE title END, updated_at = ? WHERE id = ? AND user_id = ?",
    ).bind(Number(existingCount?.count || 0), message.slice(0, 80), now, conversationId, context.user.id),
  ]);
  const workspaceId = String(payload.workspace_id || "").trim();
  const [history, examples, memories] = await Promise.all([
    recentMessages(context, conversationId),
    learnedExamples(context),
    retrieveMemory(context.env, context.user.id, message, workspaceId, 5),
  ]);
  const messages = [
    { role: "system", content: SYSTEM_PROMPT },
    ...(memories.length ? [{ role: "system", content: `บริบทจากความจำส่วนตัวของผู้ใช้ (ใช้เฉพาะเมื่อเกี่ยวข้อง และห้ามแต่งส่วนที่ไม่มี):\n\n${memories.map((item, index) => `[${index + 1}] ${item}`).join("\n\n")}` }] : []),
    ...examples.flatMap((item) => [
      { role: "user", content: item.instruction },
      { role: "assistant", content: item.ideal_response },
    ]),
    ...history.map((item) => ({ role: item.role, content: item.content })),
  ];

  let output: unknown;
  try {
    output = await (context.env.AI as unknown as { run(model: string, input: unknown): Promise<unknown> }).run(
      context.env.AI_MODEL || "@cf/google/gemma-4-26b-a4b-it",
      { messages, stream: true, max_tokens: 1_200, temperature: 0.45 },
    );
  } catch {
    await audit(context.env, context.user.id, "cloud_chat", "failed", "Workers AI request failed");
    return errorJson("MyCodex เชื่อมต่อโมเดลบนคลาวด์ไม่สำเร็จ กรุณาลองใหม่", 503);
  }

  if (!output || typeof (output as { getReader?: unknown }).getReader !== "function") {
    const answer = aiText(output).trim();
    if (!answer) return errorJson("โมเดลยังไม่ส่งคำตอบกลับมา", 503);
    await saveAssistant(context, conversationId, answer);
    await audit(context.env, context.user.id, "cloud_chat", "ok", "Cloud chat completed");
    const body = `data: ${JSON.stringify({ type: "delta", delta: answer })}\n\ndata: ${JSON.stringify({ type: "done", conversation_id: conversationId })}\n\n`;
    return secure(new Response(body, { headers: { "Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-store" } }));
  }

  const upstream = output as ReadableStream<Uint8Array>;
  const responseStream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const reader = upstream.getReader();
      const decoder = new TextDecoder();
      const encoder = new TextEncoder();
      let buffer = "";
      let answer = "";
      const emit = (delta: string) => {
        if (!delta) return;
        answer += delta;
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "delta", delta })}\n\n`));
      };
      try {
        while (true) {
          const { value, done } = await reader.read();
          buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
          const frames = buffer.split("\n\n");
          buffer = frames.pop() || "";
          for (const frame of frames) emit(streamDelta(frame));
          if (done) break;
        }
        if (buffer.trim()) emit(streamDelta(buffer));
        if (!answer.trim()) throw new Error("empty response");
        context.execution.waitUntil(saveAssistant(context, conversationId, answer));
        context.execution.waitUntil(audit(context.env, context.user!.id, "cloud_chat", "ok", "Cloud chat stream completed"));
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "done", conversation_id: conversationId })}\n\n`));
      } catch {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "error", detail: "การตอบแบบสตรีมขัดข้อง กรุณาลองใหม่" })}\n\n`));
      } finally {
        controller.close();
      }
    },
  });
  return secure(new Response(responseStream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-store",
      "Connection": "keep-alive",
    },
  }));
}

async function history(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const url = new URL(context.request.url);
  const conversationId = await conversationFor(context, url.searchParams.get("conversation") || undefined);
  const messages = await recentMessages(context, conversationId);
  return json({ conversation_id: conversationId, messages: messages.map(({ role, content }) => ({ role, content })) });
}

async function conversations(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  if (context.request.method === "POST") {
    const id = crypto.randomUUID();
    const now = epochSeconds();
    await context.env.DB.prepare(
      "INSERT INTO conversations (id, user_id, title, created_at, updated_at) VALUES (?, ?, 'แชทใหม่', ?, ?)",
    ).bind(id, context.user.id, now, now).run();
    return json({ id, title: "แชทใหม่" }, 201);
  }
  const rows = await context.env.DB.prepare(
    "SELECT id, title, created_at, updated_at FROM conversations WHERE user_id = ? ORDER BY updated_at DESC LIMIT 50",
  ).bind(context.user.id).all<{ id: string; title: string; created_at: number; updated_at: number }>();
  return json({ conversations: rows.results || [] });
}

export async function handleChat(context: RequestContext, path: string): Promise<Response | null> {
  if (path === "/api/chat/stream" && context.request.method === "POST") return streamChat(context);
  if (path === "/api/chat/history" && context.request.method === "GET") return history(context);
  if (path === "/api/chat/conversations" && ["GET", "POST"].includes(context.request.method)) return conversations(context);
  return null;
}
