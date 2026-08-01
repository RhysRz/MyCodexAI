import type { RequestContext } from "./types";
import { audit, epochSeconds, errorJson, json, readJson, secure } from "./security";

interface ImagePayload {
  prompt?: string;
  caption?: string;
}

const USER_DAILY_LIMIT = 6;
const DEFAULT_MODEL = "@cf/black-forest-labs/flux-2-klein-9b";

function promptValue(value: unknown): string {
  const prompt = String(value || "").trim();
  if (!prompt || prompt.length > 2_000) throw new Error("คำอธิบายภาพต้องมี 1-2,000 ตัวอักษร");
  return prompt;
}

function startOfUtcDay(): number {
  const now = new Date();
  return Math.floor(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()) / 1_000);
}

async function usedToday(context: RequestContext): Promise<number> {
  if (!context.user) return 0;
  const row = await context.env.DB.prepare(
    "SELECT COUNT(*) AS count FROM audit_events WHERE user_id = ? AND kind = 'image_generation' AND outcome = 'ok' AND created_at >= ?",
  ).bind(context.user.id, startOfUtcDay()).first<{ count: number }>();
  return Number(row?.count || 0);
}

function decodeImage(value: string): Uint8Array {
  const clean = value.includes(",") ? value.slice(value.indexOf(",") + 1) : value;
  const binary = atob(clean);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

function imageBytes(output: unknown): Uint8Array | null {
  if (!output || typeof output !== "object") return null;
  const record = output as Record<string, unknown>;
  if (typeof record.image === "string") return decodeImage(record.image);
  if (record.result && typeof record.result === "object") {
    const nested = record.result as Record<string, unknown>;
    if (typeof nested.image === "string") return decodeImage(nested.image);
  }
  return null;
}

async function generate(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const payload = await readJson<ImagePayload>(context.request, 12_000);
  const prompt = promptValue(payload.prompt);
  const used = await usedToday(context);
  if (context.user.role !== "admin" && used >= USER_DAILY_LIMIT) {
    return errorJson("ใช้สิทธิ์สร้างภาพครบแล้วสำหรับวันนี้ กรุณารอรอบใหม่พรุ่งนี้", 429);
  }

  const form = new FormData();
  form.append(
    "prompt",
    `${prompt}\nCreate a polished, high quality composition. Do not draw letters, words, captions, logos, watermarks, or UI text. Leave clean visual space for a separate Thai caption overlay.`,
  );
  form.append("width", "1024");
  form.append("height", "1024");
  const serialized = new Response(form);
  let output: unknown;
  try {
    output = await (context.env.AI as unknown as { run(model: string, input: unknown): Promise<unknown> }).run(
      context.env.IMAGE_MODEL || DEFAULT_MODEL,
      {
        multipart: {
          body: serialized.body,
          contentType: serialized.headers.get("content-type") || "multipart/form-data",
        },
      },
    );
  } catch {
    await audit(context.env, context.user.id, "image_generation", "failed", "Workers AI image request failed; prompt omitted");
    return errorJson("ระบบสร้างภาพบนคลาวด์ขัดข้อง กรุณาลองใหม่", 503);
  }

  const bytes = imageBytes(output);
  if (!bytes?.byteLength) {
    await audit(context.env, context.user.id, "image_generation", "failed", "Workers AI returned no image; prompt omitted");
    return errorJson("โมเดลยังไม่ส่งภาพกลับมา กรุณาลองคำอธิบายใหม่", 503);
  }
  await audit(context.env, context.user.id, "image_generation", "ok", "Cloud image generated; prompt omitted");
  const remaining = context.user.role === "admin" ? "unlimited" : String(Math.max(0, USER_DAILY_LIMIT - used - 1));
  const body = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
  return secure(new Response(body, {
    headers: {
      "Content-Type": "image/png",
      "Cache-Control": "no-store",
      "Content-Disposition": `inline; filename="mycodex-${epochSeconds()}.png"`,
      "X-Image-Remaining": remaining,
    },
  }));
}

async function status(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const used = await usedToday(context);
  return json({
    ready: true,
    model: context.env.IMAGE_MODEL || DEFAULT_MODEL,
    daily_limit: context.user.role === "admin" ? null : USER_DAILY_LIMIT,
    used_today: used,
    remaining_today: context.user.role === "admin" ? null : Math.max(0, USER_DAILY_LIMIT - used),
    quota_exempt: context.user.role === "admin",
    thai_caption_overlay: true,
  });
}

export async function handleImages(context: RequestContext, path: string): Promise<Response | null> {
  if (path === "/api/images/status" && context.request.method === "GET") return status(context);
  if (path === "/api/images/generate" && context.request.method === "POST") return generate(context);
  return null;
}
