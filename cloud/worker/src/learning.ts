import type { RequestContext } from "./types";
import { audit, epochSeconds, errorJson, readJson, secure, json } from "./security";

interface ExamplePayload {
  instruction?: string;
  ideal_response?: string;
  tags?: unknown;
}

interface EvaluationPayload {
  prompt?: string;
  expected?: string;
}

function adminOnly(context: RequestContext): Response | null {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  if (context.user.role !== "admin") return errorJson("เมนูนี้ใช้ได้เฉพาะผู้ดูแลระบบ", 403);
  return null;
}

function requiredText(value: unknown, label: string, maximum = 12_000): string {
  const text = String(value || "").trim();
  if (!text || text.length > maximum) throw new Error(`${label}ต้องมี 1-${maximum.toLocaleString("th-TH")} ตัวอักษร`);
  return text;
}

function cleanTags(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item || "").trim()).filter(Boolean).slice(0, 12).map((item) => item.slice(0, 60));
}

function parseTags(value: string): string[] {
  try {
    const parsed = JSON.parse(value) as unknown;
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [];
  }
}

async function overview(context: RequestContext): Promise<Response> {
  const denied = adminOnly(context);
  if (denied) return denied;
  const [examples, evaluations] = await Promise.all([
    context.env.DB.prepare(
      "SELECT id, instruction, ideal_response, tags_json, created_at FROM training_examples ORDER BY created_at DESC LIMIT 100",
    ).all<{ id: string; instruction: string; ideal_response: string; tags_json: string; created_at: number }>(),
    context.env.DB.prepare(
      "SELECT id, prompt, expected, created_at FROM training_evaluations ORDER BY created_at DESC LIMIT 100",
    ).all<{ id: string; prompt: string; expected: string; created_at: number }>(),
  ]);
  return json({
    examples: (examples.results || []).map((item) => ({ ...item, tags: parseTags(item.tags_json), tags_json: undefined })),
    evaluations: evaluations.results || [],
    note: "ตัวอย่างล่าสุดจะถูกใช้เป็นแนวทางการตอบของแชท Cloud โดยอัตโนมัติ",
  });
}

async function createExample(context: RequestContext): Promise<Response> {
  const denied = adminOnly(context);
  if (denied) return denied;
  const payload = await readJson<ExamplePayload>(context.request, 40_000);
  const instruction = requiredText(payload.instruction, "คำสั่งตัวอย่าง");
  const ideal = requiredText(payload.ideal_response, "คำตอบที่ต้องการ", 24_000);
  const tags = cleanTags(payload.tags);
  const id = crypto.randomUUID();
  await context.env.DB.prepare(
    "INSERT INTO training_examples (id, user_id, instruction, ideal_response, tags_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
  ).bind(id, context.user!.id, instruction, ideal, JSON.stringify(tags), epochSeconds()).run();
  await audit(context.env, context.user!.id, "training_example_added", "ok", `example=${id}`);
  return json({ id, instruction, ideal_response: ideal, tags }, 201);
}

async function createEvaluation(context: RequestContext): Promise<Response> {
  const denied = adminOnly(context);
  if (denied) return denied;
  const payload = await readJson<EvaluationPayload>(context.request, 40_000);
  const prompt = requiredText(payload.prompt, "โจทย์ประเมิน");
  const expected = requiredText(payload.expected, "เกณฑ์คำตอบ", 24_000);
  const id = crypto.randomUUID();
  await context.env.DB.prepare(
    "INSERT INTO training_evaluations (id, user_id, prompt, expected, created_at) VALUES (?, ?, ?, ?, ?)",
  ).bind(id, context.user!.id, prompt, expected, epochSeconds()).run();
  await audit(context.env, context.user!.id, "training_evaluation_added", "ok", `evaluation=${id}`);
  return json({ id, prompt, expected }, 201);
}

async function exportJsonl(context: RequestContext): Promise<Response> {
  const denied = adminOnly(context);
  if (denied) return denied;
  const rows = await context.env.DB.prepare(
    "SELECT instruction, ideal_response, tags_json FROM training_examples ORDER BY created_at ASC",
  ).all<{ instruction: string; ideal_response: string; tags_json: string }>();
  const body = (rows.results || []).map((item) => JSON.stringify({
    messages: [
      { role: "user", content: item.instruction },
      { role: "assistant", content: item.ideal_response },
    ],
    tags: parseTags(item.tags_json),
  })).join("\n");
  await audit(context.env, context.user!.id, "training_export", "ok", `examples=${rows.results?.length || 0}`);
  return secure(new Response(body ? `${body}\n` : "", {
    headers: {
      "Content-Type": "application/x-ndjson; charset=utf-8",
      "Content-Disposition": "attachment; filename=mycodex-training.jsonl",
      "Cache-Control": "no-store",
    },
  }));
}

export async function handleLearning(context: RequestContext, path: string): Promise<Response | null> {
  if (path === "/api/learning/overview" && context.request.method === "GET") return overview(context);
  if (path === "/api/learning/examples" && context.request.method === "POST") return createExample(context);
  if (path === "/api/learning/evaluations" && context.request.method === "POST") return createEvaluation(context);
  if (path === "/api/learning/export" && context.request.method === "GET") return exportJsonl(context);
  return null;
}
