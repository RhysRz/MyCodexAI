import type { CloudUser, RequestContext } from "./types";
import {
  SESSION_COOKIE,
  audit,
  clearSessionCookie,
  clientKey,
  createSession,
  epochSeconds,
  errorJson,
  hashPassword,
  json,
  parseCookies,
  randomToken,
  readJson,
  safeEqual,
  sessionCookie,
  sha256,
  verifyPassword,
} from "./security";
import {
  consumeRecoveryCode,
  createRecoveryCodes,
  createTotpSecret,
  decryptSecret,
  encryptSecret,
  recoveryHashes,
  verifyTotp,
} from "./mfa";

interface CredentialsPayload {
  username?: string;
  password?: string;
  bootstrap_token?: string;
  invite_token?: string;
  mfa_code?: string;
}

function normalizeUsername(value: unknown): string {
  const username = String(value || "").normalize("NFKC").trim();
  if (username.length < 3 || username.length > 64 || /[\u0000-\u001f\u007f]/.test(username)) {
    throw new Error("ชื่อผู้ใช้ต้องมี 3-64 ตัวอักษร");
  }
  return username;
}

function passwordValue(value: unknown): string {
  const password = String(value || "");
  if (password.length < 12 || password.length > 1_024) throw new Error("รหัสผ่านต้องมีอย่างน้อย 12 ตัวอักษร");
  return password;
}

function publicUser(user: CloudUser): CloudUser {
  return { id: user.id, username: user.username, role: user.role };
}

async function bootstrap(context: RequestContext): Promise<Response> {
  const payload = await readJson<CredentialsPayload>(context.request);
  const configuredToken = context.env.CLOUD_BOOTSTRAP_TOKEN || "";
  if (!configuredToken || !(await safeEqual(String(payload.bootstrap_token || ""), configuredToken))) {
    await audit(context.env, null, "cloud_bootstrap", "denied", "Bootstrap token rejected");
    return errorJson("โทเคนตั้งค่าครั้งแรกไม่ถูกต้อง", 403);
  }
  const existing = await context.env.DB.prepare("SELECT COUNT(*) AS count FROM users").first<{ count: number }>();
  if (Number(existing?.count || 0) > 0) return errorJson("ระบบมีบัญชีผู้ดูแลแล้ว", 409);
  const username = normalizeUsername(payload.username);
  const passwordHash = await hashPassword(passwordValue(payload.password));
  const user: CloudUser = { id: crypto.randomUUID(), username, role: "admin" };
  const now = epochSeconds();
  await context.env.DB.prepare(
    "INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?, ?, ?, 'admin', ?)",
  ).bind(user.id, user.username, passwordHash, now).run();
  const session = await createSession(context.env, user.id, context.request.headers.get("User-Agent") || "Cloud browser");
  await audit(context.env, user.id, "cloud_bootstrap", "ok", "Initial cloud administrator created");
  return json(publicUser(user), 201, { "Set-Cookie": sessionCookie(session.token, session.maxAge) });
}

async function register(context: RequestContext): Promise<Response> {
  const payload = await readJson<CredentialsPayload>(context.request);
  const username = normalizeUsername(payload.username);
  const passwordHash = await hashPassword(passwordValue(payload.password));
  const inviteHash = await sha256(String(payload.invite_token || ""));
  const now = epochSeconds();
  const invite = await context.env.DB.prepare(
    "SELECT role, expires_at FROM invites WHERE token_hash = ?",
  ).bind(inviteHash).first<{ role: "admin" | "user"; expires_at: number }>();
  if (!invite || Number(invite.expires_at) <= now) return errorJson("คำเชิญไม่ถูกต้องหรือหมดอายุแล้ว", 403);
  const user: CloudUser = { id: crypto.randomUUID(), username, role: invite.role };
  try {
    await context.env.DB.batch([
      context.env.DB.prepare(
        "INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
      ).bind(user.id, user.username, passwordHash, user.role, now),
      context.env.DB.prepare("DELETE FROM invites WHERE token_hash = ?").bind(inviteHash),
    ]);
  } catch {
    return errorJson("ชื่อผู้ใช้นี้ถูกใช้งานแล้ว", 409);
  }
  const session = await createSession(context.env, user.id, context.request.headers.get("User-Agent") || "Cloud browser");
  await audit(context.env, user.id, "cloud_register", "ok", "User registered with a one-time invite");
  return json(publicUser(user), 201, { "Set-Cookie": sessionCookie(session.token, session.maxAge) });
}

async function recordLoginFailure(context: RequestContext, key: string, now: number): Promise<void> {
  const existing = await context.env.DB.prepare(
    "SELECT failures, window_started_at FROM login_limits WHERE client_key = ?",
  ).bind(key).first<{ failures: number; window_started_at: number }>();
  const withinWindow = existing && now - Number(existing.window_started_at) <= 900;
  const failures = withinWindow ? Number(existing?.failures || 0) + 1 : 1;
  const windowStarted = withinWindow ? Number(existing?.window_started_at || now) : now;
  const blockedUntil = failures >= 5 ? now + 900 : 0;
  await context.env.DB.prepare(
    `INSERT INTO login_limits (client_key, failures, window_started_at, blocked_until)
     VALUES (?, ?, ?, ?)
     ON CONFLICT(client_key) DO UPDATE SET failures = excluded.failures,
       window_started_at = excluded.window_started_at, blocked_until = excluded.blocked_until`,
  ).bind(key, failures, windowStarted, blockedUntil).run();
}

async function login(context: RequestContext): Promise<Response> {
  const payload = await readJson<CredentialsPayload>(context.request);
  const username = normalizeUsername(payload.username);
  const password = passwordValue(payload.password);
  const key = await clientKey(context.request, username);
  const now = epochSeconds();
  const limit = await context.env.DB.prepare(
    "SELECT blocked_until FROM login_limits WHERE client_key = ?",
  ).bind(key).first<{ blocked_until: number }>();
  if (Number(limit?.blocked_until || 0) > now) {
    await audit(context.env, null, "cloud_login", "blocked", "Login temporarily rate limited");
    return errorJson("ลองเข้าสู่ระบบใหม่ภายหลัง 15 นาที", 429);
  }
  const row = await context.env.DB.prepare(
    "SELECT id, username, password_hash, role, mfa_secret_encrypted, mfa_recovery_hashes_json FROM users WHERE username = ? COLLATE NOCASE AND disabled_at IS NULL",
  ).bind(username).first<{ id: string; username: string; password_hash: string; role: "admin" | "user"; mfa_secret_encrypted: string | null; mfa_recovery_hashes_json: string }>();
  if (!row || !(await verifyPassword(row.password_hash, password))) {
    await recordLoginFailure(context, key, now);
    await audit(context.env, row?.id || null, "cloud_login", "failed", "Invalid credentials");
    return errorJson("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง", 401);
  }
  if (row.mfa_secret_encrypted) {
    const code = String(payload.mfa_code || "").trim();
    if (!code) return json({ detail: "กรอกรหัสยืนยันจากแอปหรือรหัสกู้คืน", mfa_required: true }, 428);
    let valid = false;
    try {
      valid = await verifyTotp(await decryptSecret(context.env, row.mfa_secret_encrypted), code);
    } catch { valid = false; }
    if (!valid) {
      const recovery = await consumeRecoveryCode(row.mfa_recovery_hashes_json || "[]", code);
      valid = recovery.ok;
      if (valid) {
        await context.env.DB.prepare("UPDATE users SET mfa_recovery_hashes_json = ? WHERE id = ?").bind(JSON.stringify(recovery.remaining), row.id).run();
      }
    }
    if (!valid) {
      await recordLoginFailure(context, key, now);
      await audit(context.env, row.id, "cloud_login_mfa", "failed", "Invalid MFA code");
      return json({ detail: "รหัส MFA หรือรหัสกู้คืนไม่ถูกต้อง", mfa_required: true }, 401);
    }
  }
  await context.env.DB.prepare("DELETE FROM login_limits WHERE client_key = ?").bind(key).run();
  const user: CloudUser = { id: row.id, username: row.username, role: row.role };
  const session = await createSession(context.env, user.id, context.request.headers.get("User-Agent") || "Cloud browser");
  await audit(context.env, user.id, "cloud_login", "ok", "Cloud login completed");
  return json(publicUser(user), 200, { "Set-Cookie": sessionCookie(session.token, session.maxAge) });
}

async function logout(context: RequestContext): Promise<Response> {
  const raw = parseCookies(context.request)[SESSION_COOKIE];
  if (raw) await context.env.DB.prepare("DELETE FROM sessions WHERE token_hash = ?").bind(await sha256(raw)).run();
  if (context.user) await audit(context.env, context.user.id, "cloud_logout", "ok", "Cloud session revoked");
  return json({ status: "ok" }, 200, { "Set-Cookie": clearSessionCookie() });
}

async function createInvite(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  if (context.user.role !== "admin") return errorJson("เฉพาะผู้ดูแลระบบเท่านั้น", 403);
  const payload = await readJson<{ role?: string }>(context.request);
  const role = payload.role === "admin" ? "admin" : "user";
  const token = randomToken(24);
  const now = epochSeconds();
  const expiresAt = now + 24 * 60 * 60;
  await context.env.DB.prepare(
    "INSERT INTO invites (token_hash, role, created_by, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
  ).bind(await sha256(token), role, context.user.id, expiresAt, now).run();
  await audit(context.env, context.user.id, "invite_created", "ok", `Created a one-time ${role} invite`);
  return json({ token, role, expires_at: new Date(expiresAt * 1_000).toISOString() }, 201);
}

async function listSessions(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const raw = parseCookies(context.request)[SESSION_COOKIE] || "";
  const currentHash = raw ? await sha256(raw) : "";
  const sessions = await context.env.DB.prepare(
    "SELECT token_hash, device_label, created_at, last_seen_at FROM sessions WHERE user_id = ? ORDER BY last_seen_at DESC",
  ).bind(context.user.id).all<{ token_hash: string; device_label: string; created_at: number; last_seen_at: number }>();
  return json({
    sessions: (sessions.results || []).map((row) => ({
      device_label: row.device_label,
      created_at: new Date(Number(row.created_at) * 1_000).toISOString(),
      last_seen_at: new Date(Number(row.last_seen_at) * 1_000).toISOString(),
      current: row.token_hash === currentHash,
    })),
  });
}

async function revokeOtherSessions(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const raw = parseCookies(context.request)[SESSION_COOKIE] || "";
  const currentHash = raw ? await sha256(raw) : "";
  const result = await context.env.DB.prepare(
    "DELETE FROM sessions WHERE user_id = ? AND token_hash != ?",
  ).bind(context.user.id, currentHash).run();
  await audit(context.env, context.user.id, "sessions_revoked", "ok", "Other cloud sessions revoked");
  return json({ revoked: Number(result.meta.changes || 0) });
}

async function mfaStatus(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const row = await context.env.DB.prepare(
    "SELECT mfa_secret_encrypted, mfa_pending_encrypted, mfa_recovery_hashes_json FROM users WHERE id = ?",
  ).bind(context.user.id).first<{ mfa_secret_encrypted: string | null; mfa_pending_encrypted: string | null; mfa_recovery_hashes_json: string }>();
  let recoveryCount = 0;
  try {
    const parsed = JSON.parse(row?.mfa_recovery_hashes_json || "[]") as unknown;
    recoveryCount = Array.isArray(parsed) ? parsed.length : 0;
  } catch { recoveryCount = 0; }
  return json({ enabled: Boolean(row?.mfa_secret_encrypted), pending: Boolean(row?.mfa_pending_encrypted), recovery_codes_remaining: recoveryCount });
}

async function setupMfa(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const current = await context.env.DB.prepare("SELECT mfa_secret_encrypted FROM users WHERE id = ?").bind(context.user.id).first<{ mfa_secret_encrypted: string | null }>();
  if (current?.mfa_secret_encrypted) return errorJson("บัญชีนี้เปิดใช้งาน MFA แล้ว", 409);
  const secret = createTotpSecret();
  await context.env.DB.prepare("UPDATE users SET mfa_pending_encrypted = ? WHERE id = ?").bind(await encryptSecret(context.env, secret), context.user.id).run();
  const label = encodeURIComponent(`MyCodexAI Cloud:${context.user.username}`);
  const issuer = encodeURIComponent("MyCodexAI Cloud");
  await audit(context.env, context.user.id, "mfa_setup", "pending", "MFA setup started; secret omitted");
  return json({ secret, otpauth_url: `otpauth://totp/${label}?secret=${secret}&issuer=${issuer}&algorithm=SHA1&digits=6&period=30` });
}

async function enableMfa(context: RequestContext): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  const payload = await readJson<{ code?: string }>(context.request, 8_000);
  const row = await context.env.DB.prepare("SELECT mfa_pending_encrypted FROM users WHERE id = ?").bind(context.user.id).first<{ mfa_pending_encrypted: string | null }>();
  if (!row?.mfa_pending_encrypted) return errorJson("กรุณาเริ่มตั้งค่า MFA ก่อน", 409);
  let secret: string;
  try { secret = await decryptSecret(context.env, row.mfa_pending_encrypted); } catch { return errorJson("อ่านข้อมูลตั้งค่า MFA ไม่สำเร็จ", 500); }
  if (!(await verifyTotp(secret, String(payload.code || "")))) return errorJson("รหัส 6 หลักไม่ถูกต้องหรือหมดเวลาแล้ว", 400);
  const recoveryCodes = createRecoveryCodes();
  const rawSession = parseCookies(context.request)[SESSION_COOKIE];
  if (!rawSession) return errorJson("เซสชันหมดอายุ กรุณาเข้าสู่ระบบใหม่", 401);
  await context.env.DB.batch([
    context.env.DB.prepare(
      "UPDATE users SET mfa_secret_encrypted = ?, mfa_pending_encrypted = NULL, mfa_recovery_hashes_json = ? WHERE id = ?",
    ).bind(await encryptSecret(context.env, secret), JSON.stringify(await recoveryHashes(recoveryCodes)), context.user.id),
    context.env.DB.prepare("DELETE FROM sessions WHERE user_id = ? AND token_hash != ?").bind(
      context.user.id,
      await sha256(rawSession),
    ),
  ]);
  await audit(context.env, context.user.id, "mfa_enabled", "ok", "Cloud MFA enabled; recovery codes omitted");
  return json({ enabled: true, recovery_codes: recoveryCodes });
}

export async function handleAuth(context: RequestContext, path: string): Promise<Response | null> {
  if (path === "/api/auth/bootstrap" && context.request.method === "POST") return bootstrap(context);
  if (path === "/api/auth/register" && context.request.method === "POST") return register(context);
  if (path === "/api/auth/login" && context.request.method === "POST") return login(context);
  if (path === "/api/auth/logout" && context.request.method === "POST") return logout(context);
  if (path === "/api/auth/me" && context.request.method === "GET") {
    return context.user ? json(publicUser(context.user)) : errorJson("ต้องเข้าสู่ระบบ", 401);
  }
  if (path === "/api/auth/invites" && context.request.method === "POST") return createInvite(context);
  if (path === "/api/auth/sessions" && context.request.method === "GET") return listSessions(context);
  if (path === "/api/auth/sessions/revoke-others" && context.request.method === "POST") return revokeOtherSessions(context);
  if (path === "/api/auth/mfa" && context.request.method === "GET") return mfaStatus(context);
  if (path === "/api/auth/mfa/setup" && context.request.method === "POST") return setupMfa(context);
  if (path === "/api/auth/mfa/enable" && context.request.method === "POST") return enableMfa(context);
  if (path === "/api/auth/oauth/providers" && context.request.method === "GET") {
    return json({ providers: { google: false, github: false } });
  }
  return null;
}
