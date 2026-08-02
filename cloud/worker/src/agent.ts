import type { AgentQueueMessage, AgentRunRow, RequestContext, Env } from "./types";
import { audit, epochSeconds, errorJson, json, readJson, safeEqual } from "./security";
import { notifyUser } from "./notifications";
import { publishEvent } from "./realtime";

const MODES = new Set(["agent", "codex", "project", "expert", "delivery", "team", "review"]);
const FINAL_STATUSES = new Set(["completed", "failed", "needs_review", "cancelled"]);

interface RunPayload {
  task?: string;
  mode?: string;
  attachments?: unknown[];
  background?: boolean;
  review_scope?: string;
  review_target?: string;
  workspace_id?: string;
  goal?: string;
  context?: string;
  constraints?: string;
  done_when?: string;
  reasoning_effort?: string;
  plan_first?: boolean;
  verify?: boolean;
}

interface DraftFile {
  path: string;
  content: string;
}

function parseArray(value: string | null): unknown[] {
  try {
    const parsed = JSON.parse(value || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function cleanTask(value: unknown): string {
  const task = String(value || "").trim();
  if (!task || task.length > 20_000) throw new Error("คำสั่ง Agent ต้องมี 1-20,000 ตัวอักษร");
  return task;
}

function cleanAttachments(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.slice(0, 20).map((item) => String(item)).filter((item) => /^[a-f0-9-]{20,64}$/i.test(item));
}

async function queuePosition(env: Env, row: AgentRunRow): Promise<number | null> {
  if (!["queued", "dispatching", "dispatched"].includes(row.status)) return null;
  const position = await env.DB.prepare(
    "SELECT COUNT(*) AS count FROM agent_runs WHERE status IN ('queued', 'dispatching', 'dispatched') AND created_at <= ?",
  ).bind(row.created_at).first<{ count: number }>();
  return Math.max(1, Number(position?.count || 1));
}

async function runResponse(env: Env, row: AgentRunRow): Promise<Record<string, unknown>> {
  const trace = parseArray(row.trace_json);
  const attachments = parseArray(row.attachments_json).map(String);
  const position = await queuePosition(env, row);
  const answerParts = [row.answer || ""];
  if (row.pull_request_url) answerParts.push(`Pull request: ${row.pull_request_url}`);
  if (row.error_detail) answerParts.push(row.error_detail);
  return {
    run_id: row.id,
    task: row.task,
    mode: MODES.has(row.mode) ? row.mode : "agent",
    background: true,
    review_scope: "uncommitted",
    review_target: "",
    workspace_id: "cloud",
    project_id: "MyCodexAI",
    status: row.status,
    answer: answerParts.filter(Boolean).join("\n\n") || null,
    trace,
    pending_action: null,
    workflow: (() => { try { return JSON.parse(row.workflow_json || "{}"); } catch { return {}; } })(),
    project_plan: (() => { try { return JSON.parse(row.project_plan_json || "null"); } catch { return null; } })(),
    team_members: [],
    progress: {
      current: trace.length,
      total: Math.max(1, trace.length),
      queue_position: position,
      phase: row.status,
      pull_request_url: row.pull_request_url,
      branch_name: row.branch_name,
      attempts: Number(row.attempt_count || 0),
    },
    activity: FINAL_STATUSES.has(row.status) ? null : {
      kind: row.status,
      detail: row.status === "queued" ? "งานอยู่ในคิวส่วนตัวของ MyCodexAI" : "GitHub Runner กำลังดำเนินงาน",
    },
    attachments,
    delivery_phase: row.status,
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

async function getOwnedRun(context: RequestContext, runId: string): Promise<AgentRunRow | null> {
  if (!context.user) return null;
  return context.env.DB.prepare(
    "SELECT * FROM agent_runs WHERE id = ? AND user_id = ?",
  ).bind(runId, context.user.id).first<AgentRunRow>();
}

async function createRun(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const payload = await readJson<RunPayload>(context.request, 64_000);
  const task = cleanTask(payload.task);
  const mode = MODES.has(String(payload.mode || "codex")) ? String(payload.mode || "codex") : "codex";
  const attachments = cleanAttachments(payload.attachments);
  const workspaceId = String(payload.workspace_id || "").trim();
  if (workspaceId) {
    const workspace = await context.env.DB.prepare("SELECT id FROM cloud_workspaces WHERE id = ? AND user_id = ?")
      .bind(workspaceId, context.user.id).first();
    if (!workspace) return errorJson("ไม่พบ Cloud Workspace ที่เลือก", 404);
  }
  const effort = ["low", "medium", "high"].includes(String(payload.reasoning_effort)) ? String(payload.reasoning_effort) : "high";
  const workflow = {
    goal: String(payload.goal || task).trim().slice(0, 20_000),
    context: String(payload.context || "").trim().slice(0, 20_000),
    constraints: String(payload.constraints || "รักษาความปลอดภัย ไม่แก้ secret และคงความเข้ากันได้เดิม").trim().slice(0, 12_000),
    done_when: String(payload.done_when || "ทดสอบที่เกี่ยวข้องผ่าน ตรวจ diff แล้ว และเปิด Pull Request ให้ผู้ใช้ตรวจ").trim().slice(0, 12_000),
    reasoning_effort: effort,
    plan_first: payload.plan_first !== false,
    verify: payload.verify !== false,
    approval_policy: "pull-request-review",
  };
  const projectPlan = [
    { step: "สำรวจ repository และอ่านบริบทที่เกี่ยวข้อง", status: "pending" },
    { step: mode === "review" ? "ตรวจ diff และหาความเสี่ยงโดยไม่แก้ไฟล์" : "แก้ไขแบบเจาะจงบน branch แยก", status: "pending" },
    { step: "รันการตรวจสอบที่กำหนดและเก็บหลักฐาน", status: "pending" },
    { step: "สรุป diff และส่งให้ผู้ใช้ตรวจผ่าน Pull Request", status: "pending" },
  ];
  const now = epochSeconds();
  if (context.user.role !== "admin") {
    const dayStart = now - (now % 86_400);
    const usage = await context.env.DB.prepare(
      "SELECT COUNT(*) AS count FROM agent_runs WHERE user_id = ? AND created_at >= ?",
    ).bind(context.user.id, dayStart).first<{ count: number }>();
    const limit = Math.max(1, Number.parseInt(context.env.AGENT_DAILY_LIMIT || "12", 10) || 12);
    if (Number(usage?.count || 0) >= limit) return errorJson("โควต้างาน Agent วันนี้ครบแล้ว กรุณารอรอบถัดไป", 429);
  }
  const runId = crypto.randomUUID();
  const trace = [{ kind: "queued", status: "ok", summary: "รับงานเข้าสู่คิว Cloud Agent แล้ว" }];
  await context.env.DB.prepare(
    `INSERT INTO agent_runs
      (id, user_id, task, mode, status, trace_json, attachments_json, workspace_id, workflow_json, project_plan_json, created_at, updated_at)
     VALUES (?, ?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?)`,
  ).bind(
    runId, context.user.id, task, mode, JSON.stringify(trace), JSON.stringify(attachments), workspaceId || null,
    JSON.stringify(workflow), JSON.stringify(projectPlan), now, now,
  ).run();
  try {
    await context.env.AGENT_QUEUE.send({ kind: "agent", runId });
  } catch {
    await context.env.DB.prepare(
      "UPDATE agent_runs SET status = 'failed', error_detail = ?, updated_at = ?, completed_at = ? WHERE id = ?",
    ).bind("ไม่สามารถส่งงานเข้าคิว Cloudflare ได้", now, now, runId).run();
    return errorJson("ไม่สามารถส่งงานเข้าคิวได้ กรุณาลองใหม่", 503);
  }
  await audit(context.env, context.user.id, "agent_queued", "ok", "Cloud agent job queued");
  context.execution.waitUntil(publishEvent(context.env, context.user.id, {
    type: "agent_progress", title: "รับงานเข้า Codex workflow แล้ว", detail: task.slice(0, 180),
    resource_id: runId, status: "queued", progress: 5, action_url: "/?view=agent",
  }));
  const row = await getOwnedRun(context, runId);
  return json(await runResponse(context.env, row!), 202);
}

async function listRuns(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const rows = await context.env.DB.prepare(
    "SELECT * FROM agent_runs WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
  ).bind(context.user.id).all<AgentRunRow>();
  const runs = [];
  for (const row of rows.results || []) runs.push(await runResponse(context.env, row));
  return json({ runs });
}

async function usage(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const now = epochSeconds();
  const dayStart = now - (now % 86_400);
  const count = await context.env.DB.prepare(
    "SELECT COUNT(*) AS runs FROM agent_runs WHERE user_id = ? AND created_at >= ?",
  ).bind(context.user.id, dayStart).first<{ runs: number }>();
  const limit = context.user.role === "admin" ? 0 : Math.max(1, Number.parseInt(context.env.AGENT_DAILY_LIMIT || "12", 10) || 12);
  return json({
    date: new Date(now * 1_000).toISOString().slice(0, 10),
    runs: Number(count?.runs || 0),
    run_limit: limit,
    steps: 0,
    step_limit: 0,
    runs_limited: context.user.role !== "admin",
    steps_limited: false,
    quota_exempt: context.user.role === "admin",
  });
}

async function activity(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const events = await context.env.DB.prepare(
    "SELECT kind, outcome, detail, created_at FROM audit_events WHERE user_id = ? ORDER BY created_at DESC LIMIT 30",
  ).bind(context.user.id).all<{ kind: string; outcome: string; detail: string; created_at: number }>();
  return json({ events: events.results || [] });
}

async function cancelRun(context: RequestContext, runId: string): Promise<Response> {
  const row = await getOwnedRun(context, runId);
  if (!row) return errorJson("ไม่พบงาน Agent", 404);
  if (!["queued", "dispatching"].includes(row.status)) return errorJson("งานเริ่มทำแล้วและไม่สามารถยกเลิกจากคิวได้", 409);
  const now = epochSeconds();
  await context.env.DB.prepare(
    "UPDATE agent_runs SET status = 'cancelled', answer = ?, updated_at = ?, completed_at = ? WHERE id = ? AND user_id = ?",
  ).bind("ยกเลิกงานก่อนเริ่มทำแล้ว", now, now, runId, context.user!.id).run();
  const updated = await getOwnedRun(context, runId);
  return json(await runResponse(context.env, updated!));
}

function bearer(request: Request): string {
  const authorization = request.headers.get("Authorization") || "";
  return authorization.startsWith("Bearer ") ? authorization.slice(7) : "";
}

async function runnerAuthorized(request: Request, env: Env): Promise<boolean> {
  return Boolean(env.RUNNER_CALLBACK_SECRET) && safeEqual(bearer(request), env.RUNNER_CALLBACK_SECRET);
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
  return typeof message?.content === "string" ? message.content : "";
}

function extractJson(text: string): Record<string, unknown> {
  const clean = text.trim().replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/i, "");
  const start = clean.indexOf("{");
  const end = clean.lastIndexOf("}");
  if (start < 0 || end <= start) throw new Error("โมเดลไม่ได้ส่งแผนแก้ไขเป็น JSON");
  return JSON.parse(clean.slice(start, end + 1)) as Record<string, unknown>;
}

function safeDraftFiles(value: unknown): DraftFile[] {
  if (!Array.isArray(value)) return [];
  const files: DraftFile[] = [];
  let total = 0;
  for (const raw of value.slice(0, 20)) {
    if (!raw || typeof raw !== "object") continue;
    const item = raw as Record<string, unknown>;
    const path = String(item.path || "").replace(/\\/g, "/").replace(/^\.\//, "");
    const content = String(item.content ?? "");
    if (!path || path.startsWith("/") || path.includes("../") || path === ".env" || path.startsWith(".git/") || path.startsWith(".github/workflows/")) continue;
    if (path.length > 240 || content.length > 250_000) continue;
    total += content.length;
    if (total > 600_000) break;
    files.push({ path, content });
  }
  return files;
}

async function draft(context: RequestContext): Promise<Response> {
  if (!(await runnerAuthorized(context.request, context.env))) return errorJson("Runner authentication failed", 401);
  const payload = await readJson<{
    run_id?: string;
    files?: Array<{ path?: string; content?: string }>;
    manifest?: string[];
  }>(context.request, 900_000);
  const runId = String(payload.run_id || "");
  const run = await context.env.DB.prepare("SELECT * FROM agent_runs WHERE id = ?").bind(runId).first<AgentRunRow>();
  if (!run) return errorJson("Agent run not found", 404);
  const inputFiles = Array.isArray(payload.files) ? payload.files.slice(0, 60) : [];
  let used = 0;
  const contextFiles: string[] = [];
  for (const file of inputFiles) {
    const path = String(file.path || "").slice(0, 240);
    const content = String(file.content || "").slice(0, 30_000);
    used += path.length + content.length;
    if (used > 220_000) break;
    contextFiles.push(`\n--- FILE: ${path} ---\n${content}`);
  }
  const system = `You are MyCodex Cloud Agent, a senior software engineer operating through a reviewed GitHub pull request.
Return only one JSON object with this schema: {"summary":"Thai summary","files":[{"path":"relative/path","content":"complete file content"}],"notes":["Thai note"]}.
Use complete file contents, never partial snippets. Modify at most 20 files. Never create or modify .env, credentials, tokens, .git paths, or .github/workflows.
Do not claim tests passed. The runner will execute fixed checks. Prefer focused, secure and maintainable changes. Explain summary and notes in correct Thai.
Codex workflow means: inspect before editing, follow durable repository guidance, keep changes scoped, preserve user work, verify the result, review the final diff, and stop at a Pull Request for human approval.
For review mode, return no modified files and provide findings in summary/notes only. For project mode, create a complete but focused project foundation. For team mode, reason through explorer, implementer, tester and reviewer roles sequentially.`;
  const prompt = `TASK (${run.mode}):\n${run.task}\n\nWORKFLOW:\n${run.workflow_json || "{}"}\n\nREPOSITORY MANIFEST:\n${(payload.manifest || []).slice(0, 500).join("\n")}\n\nSELECTED FILE CONTENTS:${contextFiles.join("")}`;
  let output: unknown;
  try {
    output = await (context.env.AI as unknown as { run(model: string, input: unknown): Promise<unknown> }).run(
      context.env.AI_MODEL || "@cf/google/gemma-4-26b-a4b-it",
      { messages: [{ role: "system", content: system }, { role: "user", content: prompt }], max_tokens: 7_500, temperature: 0.2 },
    );
  } catch {
    return errorJson("Workers AI could not prepare the code change", 503);
  }
  try {
    const parsed = extractJson(aiText(output));
    const files = safeDraftFiles(parsed.files);
    if (!files.length && run.mode !== "review") return errorJson("โมเดลยังไม่ได้ส่งไฟล์ที่แก้ไขกลับมา", 422);
    return json({ summary: String(parsed.summary || "เตรียมการแก้ไขแล้ว").slice(0, 2_000), files, notes: Array.isArray(parsed.notes) ? parsed.notes.slice(0, 20).map(String) : [] });
  } catch (error) {
    return errorJson(error instanceof Error ? error.message : "ไม่สามารถอ่านผลลัพธ์ของโมเดลได้", 422);
  }
}

async function callback(context: RequestContext): Promise<Response> {
  if (!(await runnerAuthorized(context.request, context.env))) return errorJson("Runner authentication failed", 401);
  const payload = await readJson<{
    run_id?: string;
    status?: string;
    answer?: string;
    pull_request_url?: string;
    branch_name?: string;
    error_detail?: string;
    trace?: unknown[];
  }>(context.request, 128_000);
  const runId = String(payload.run_id || "");
  const allowed = new Set(["running", "completed", "failed", "needs_review", "cancelled"]);
  const status = allowed.has(String(payload.status)) ? String(payload.status) : "failed";
  const current = await context.env.DB.prepare("SELECT user_id FROM agent_runs WHERE id = ?").bind(runId).first<{ user_id: string }>();
  if (!current) return errorJson("Agent run not found", 404);
  const now = epochSeconds();
  const completedAt = FINAL_STATUSES.has(status) ? now : null;
  await context.env.DB.prepare(
    `UPDATE agent_runs SET status = ?, answer = ?, pull_request_url = ?, branch_name = ?,
      error_detail = ?, trace_json = ?, updated_at = ?, started_at = COALESCE(started_at, ?), completed_at = ?
      WHERE id = ?`,
  ).bind(
    status,
    String(payload.answer || "").slice(0, 20_000) || null,
    String(payload.pull_request_url || "").slice(0, 500) || null,
    String(payload.branch_name || "").slice(0, 240) || null,
    String(payload.error_detail || "").slice(0, 4_000) || null,
    JSON.stringify(Array.isArray(payload.trace) ? payload.trace.slice(0, 100) : []),
    now,
    now,
    completedAt,
    runId,
  ).run();
  await audit(context.env, current.user_id, "agent_callback", status, "GitHub runner updated cloud agent status");
  if (FINAL_STATUSES.has(status)) {
    context.execution.waitUntil(notifyUser(context.env, current.user_id, {
      type: "agent_complete",
      title: status === "needs_review" ? "Codex workflow พร้อมให้ตรวจแล้ว" : status === "completed" ? "Cloud Agent ทำงานเสร็จแล้ว" : "Cloud Agent หยุดทำงาน",
      detail: String(payload.answer || payload.error_detail || "").slice(0, 500), resource_id: runId, status,
      progress: 100, action_url: "/?view=agent",
    }));
  } else {
    context.execution.waitUntil(publishEvent(context.env, current.user_id, {
      type: "agent_progress", title: "Codex workflow กำลังทำงาน", resource_id: runId, status,
      progress: status === "running" ? 55 : 25, action_url: "/?view=agent",
    }));
  }
  return json({ status: "ok" });
}

export async function handleAgent(context: RequestContext, path: string): Promise<Response | null> {
  if (path === "/api/agent/runs" && context.request.method === "POST") return createRun(context);
  if (path === "/api/agent/runs" && context.request.method === "GET") return listRuns(context);
  if (path === "/api/agent/usage" && context.request.method === "GET") return usage(context);
  if (path === "/api/agent/activity" && context.request.method === "GET") return activity(context);
  const match = path.match(/^\/api\/agent\/runs\/([a-f0-9-]+)(?:\/(cancel|continue|resume))?$/i);
  if (match && context.request.method === "GET" && !match[2]) {
    const row = await getOwnedRun(context, match[1]);
    return row ? json(await runResponse(context.env, row)) : errorJson("ไม่พบงาน Agent", 404);
  }
  if (match && context.request.method === "POST" && match[2] === "cancel") return cancelRun(context, match[1]);
  if (match && context.request.method === "POST" && ["continue", "resume"].includes(match[2] || "")) {
    return errorJson("งาน Cloud Agent ทำงานผ่าน Pull Request และไม่ต้องอนุมัติคำสั่งย่อย", 409);
  }
  if (path === "/api/internal/agent/draft" && context.request.method === "POST") return draft(context);
  if (path === "/api/internal/agent/callback" && context.request.method === "POST") return callback(context);
  return null;
}

export async function consumeAgentQueue(batch: MessageBatch<AgentQueueMessage>, env: Env): Promise<void> {
  for (const message of batch.messages) {
    if (message.body.kind && message.body.kind !== "agent") { message.retry({ delaySeconds: 15 }); continue; }
    const runId = String(message.body.runId || "");
    const run = await env.DB.prepare("SELECT * FROM agent_runs WHERE id = ?").bind(runId).first<AgentRunRow>();
    if (!run || run.status === "cancelled" || FINAL_STATUSES.has(run.status)) {
      message.ack();
      continue;
    }
    if (!env.GITHUB_TOKEN || !env.GITHUB_OWNER || !env.GITHUB_REPO || env.GITHUB_OWNER.startsWith("REPLACE_") || env.GITHUB_REPO.startsWith("REPLACE_")) {
      const now = epochSeconds();
      await env.DB.prepare(
        "UPDATE agent_runs SET status = 'failed', error_detail = ?, updated_at = ?, completed_at = ? WHERE id = ?",
      ).bind("ยังไม่ได้ตั้งค่า GitHub repository หรือโทเคนสำหรับ Cloud Agent", now, now, run.id).run();
      message.ack();
      continue;
    }
    const now = epochSeconds();
    await env.DB.prepare("UPDATE agent_runs SET status = 'dispatching', attempt_count = attempt_count + 1, updated_at = ? WHERE id = ?").bind(now, run.id).run();
    const response = await fetch(`https://api.github.com/repos/${encodeURIComponent(env.GITHUB_OWNER)}/${encodeURIComponent(env.GITHUB_REPO)}/dispatches`, {
      method: "POST",
      headers: {
        "Accept": "application/vnd.github+json",
        "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
        "Content-Type": "application/json",
        "User-Agent": "MyCodexAI-Cloud/1.0",
        "X-GitHub-Api-Version": "2026-03-10",
      },
      body: JSON.stringify({
        event_type: "mycodexai-agent",
        client_payload: {
          run_id: run.id,
          task: run.task.slice(0, 20_000),
          mode: run.mode,
          attachments: parseArray(run.attachments_json).slice(0, 20),
          workspace_id: run.workspace_id || "",
          workflow: (() => { try { return JSON.parse(run.workflow_json || "{}"); } catch { return {}; } })(),
        },
      }),
    });
    if (!response.ok) {
      await env.DB.prepare("UPDATE agent_runs SET status = 'queued', updated_at = ? WHERE id = ?").bind(epochSeconds(), run.id).run();
      message.retry({ delaySeconds: Math.min(300, 15 * message.attempts) });
      continue;
    }
    const trace = [...parseArray(run.trace_json), { kind: "github_dispatch", status: "ok", summary: "ส่งงานให้ GitHub Runner แล้ว" }];
    await env.DB.prepare(
      "UPDATE agent_runs SET status = 'dispatched', trace_json = ?, updated_at = ? WHERE id = ?",
    ).bind(JSON.stringify(trace), epochSeconds(), run.id).run();
    message.ack();
  }
}
