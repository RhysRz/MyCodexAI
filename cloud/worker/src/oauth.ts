import type { Env, RequestContext } from "./types";
import {
  audit,
  createSession,
  epochSeconds,
  errorJson,
  json,
  parseCookies,
  randomToken,
  readJson,
  safeEqual,
  sessionCookie,
  sha256,
} from "./security";
import { consumeRecoveryCode, decryptSecret, verifyTotp } from "./mfa";

const STATE_COOKIE = "__Host-mycodexai_oauth_state";
const MFA_COOKIE = "__Host-mycodexai_oauth_mfa";
const STATE_TTL = 600;

type ProviderName = "google" | "github";

interface ProviderConfig {
  name: ProviderName;
  clientId: string;
  clientSecret: string;
  authorizationUrl: string;
  tokenUrl: string;
  scope: string;
}

interface OAuthStateRow {
  provider: ProviderName;
  action: "login" | "link";
  user_id: string | null;
  code_verifier: string;
}

interface Identity {
  subject: string;
  email: string | null;
}

function providerConfig(env: Env, name: string): ProviderConfig | null {
  if (name === "google") {
    const clientId = (env.OAUTH_GOOGLE_CLIENT_ID || "").trim();
    const clientSecret = (env.OAUTH_GOOGLE_CLIENT_SECRET || "").trim();
    return clientId && clientSecret ? {
      name: "google", clientId, clientSecret,
      authorizationUrl: "https://accounts.google.com/o/oauth2/v2/auth",
      tokenUrl: "https://oauth2.googleapis.com/token",
      scope: "openid email profile",
    } : null;
  }
  if (name === "github") {
    const clientId = (env.OAUTH_GITHUB_CLIENT_ID || "").trim();
    const clientSecret = (env.OAUTH_GITHUB_CLIENT_SECRET || "").trim();
    return clientId && clientSecret ? {
      name: "github", clientId, clientSecret,
      authorizationUrl: "https://github.com/login/oauth/authorize",
      tokenUrl: "https://github.com/login/oauth/access_token",
      scope: "read:user",
    } : null;
  }
  return null;
}

function publicOrigin(context: RequestContext): string {
  return (context.env.PUBLIC_ORIGIN || new URL(context.request.url).origin).replace(/\/$/, "");
}

function callbackUrl(context: RequestContext, provider: ProviderName): string {
  return `${publicOrigin(context)}/api/auth/oauth/${provider}/callback`;
}

function stateCookie(value: string, maxAge = STATE_TTL): string {
  return `${STATE_COOKIE}=${encodeURIComponent(value)}; Path=/; Max-Age=${maxAge}; Secure; HttpOnly; SameSite=Lax`;
}

function mfaCookie(value: string, maxAge = STATE_TTL): string {
  return `${MFA_COOKIE}=${encodeURIComponent(value)}; Path=/; Max-Age=${maxAge}; Secure; HttpOnly; SameSite=Strict`;
}

function redirect(location: string, cookies: string[] = []): Response {
  const headers = new Headers({ Location: location, "Cache-Control": "no-store" });
  cookies.forEach((cookie) => headers.append("Set-Cookie", cookie));
  return new Response(null, { status: 302, headers });
}

function jsonWithCookies(data: unknown, status: number, cookies: string[]): Response {
  const response = json(data, status);
  const headers = new Headers(response.headers);
  cookies.forEach((cookie) => headers.append("Set-Cookie", cookie));
  return new Response(response.body, { status: response.status, headers });
}

async function providerStatus(context: RequestContext): Promise<Response> {
  const configured = {
    google: Boolean(providerConfig(context.env, "google")),
    github: Boolean(providerConfig(context.env, "github")),
  };
  const linked = { google: false, github: false };
  if (context.user) {
    const rows = await context.env.DB.prepare(
      "SELECT provider FROM oauth_identities WHERE user_id = ?",
    ).bind(context.user.id).all<{ provider: ProviderName }>();
    for (const row of rows.results || []) linked[row.provider] = true;
  }
  return json({
    providers: {
      google: { configured: configured.google, linked: linked.google },
      github: { configured: configured.github, linked: linked.github },
    },
  });
}

async function begin(context: RequestContext, providerName: string, action: "login" | "link"): Promise<Response> {
  const provider = providerConfig(context.env, providerName);
  if (!provider) return errorJson("ยังไม่ได้ตั้งค่า Social Login ผู้ให้บริการนี้", 503);
  if (action === "link" && !context.user) return errorJson("ต้องเข้าสู่ระบบก่อนเชื่อมบัญชี", 401);
  const state = randomToken(32);
  const codeVerifier = randomToken(48);
  const now = epochSeconds();
  await context.env.DB.prepare(
    "INSERT INTO oauth_states (token_hash, provider, action, user_id, code_verifier, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
  ).bind(await sha256(state), provider.name, action, context.user?.id || null, codeVerifier, now, now + STATE_TTL).run();
  const authorization = new URL(provider.authorizationUrl);
  authorization.searchParams.set("client_id", provider.clientId);
  authorization.searchParams.set("redirect_uri", callbackUrl(context, provider.name));
  authorization.searchParams.set("response_type", "code");
  authorization.searchParams.set("scope", provider.scope);
  authorization.searchParams.set("state", state);
  authorization.searchParams.set("code_challenge", await sha256(codeVerifier));
  authorization.searchParams.set("code_challenge_method", "S256");
  if (provider.name === "google") authorization.searchParams.set("prompt", "select_account");
  if (provider.name === "github") authorization.searchParams.set("allow_signup", "false");
  await audit(context.env, context.user?.id || null, `oauth_${action}_started`, "ok", `provider=${provider.name}`);
  const cookie = stateCookie(state);
  return action === "login"
    ? redirect(authorization.toString(), [cookie])
    : json({ authorization_url: authorization.toString() }, 200, { "Set-Cookie": cookie });
}

async function consumeState(context: RequestContext, provider: ProviderName, queryState: string): Promise<OAuthStateRow | null> {
  const cookieState = parseCookies(context.request)[STATE_COOKIE] || "";
  if (!queryState || !cookieState || !(await safeEqual(queryState, cookieState))) return null;
  const tokenHash = await sha256(queryState);
  const row = await context.env.DB.prepare(
    "SELECT provider, action, user_id, code_verifier FROM oauth_states WHERE token_hash = ? AND expires_at > ?",
  ).bind(tokenHash, epochSeconds()).first<OAuthStateRow>();
  await context.env.DB.prepare("DELETE FROM oauth_states WHERE token_hash = ?").bind(tokenHash).run();
  return row?.provider === provider ? row : null;
}

async function exchangeCode(context: RequestContext, provider: ProviderConfig, code: string, state: OAuthStateRow): Promise<string> {
  const body = new URLSearchParams({
    client_id: provider.clientId,
    client_secret: provider.clientSecret,
    code,
    redirect_uri: callbackUrl(context, provider.name),
    code_verifier: state.code_verifier,
    grant_type: "authorization_code",
  });
  const response = await fetch(provider.tokenUrl, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  const payload = await response.json().catch(() => ({})) as Record<string, unknown>;
  const accessToken = String(payload.access_token || "");
  if (!response.ok || !accessToken) throw new Error("OAuth token exchange failed");
  return accessToken;
}

async function fetchIdentity(provider: ProviderConfig, accessToken: string): Promise<Identity> {
  const endpoint = provider.name === "google"
    ? "https://openidconnect.googleapis.com/v1/userinfo"
    : "https://api.github.com/user";
  const response = await fetch(endpoint, { headers: {
    Accept: "application/json",
    Authorization: `Bearer ${accessToken}`,
    "User-Agent": "MyCodexAI-Cloud/1.0",
    ...(provider.name === "github" ? { "X-GitHub-Api-Version": "2026-03-10" } : {}),
  } });
  const payload = await response.json().catch(() => ({})) as Record<string, unknown>;
  const subject = provider.name === "google" ? String(payload.sub || "") : String(payload.id || "");
  if (!response.ok || !subject) throw new Error("OAuth identity request failed");
  return { subject: subject.slice(0, 200), email: payload.email ? String(payload.email).slice(0, 320) : null };
}

async function linkIdentity(context: RequestContext, provider: ProviderName, userId: string, identity: Identity): Promise<boolean> {
  const owner = await context.env.DB.prepare(
    "SELECT user_id FROM oauth_identities WHERE provider = ? AND subject = ?",
  ).bind(provider, identity.subject).first<{ user_id: string }>();
  if (owner && owner.user_id !== userId) return false;
  const existing = await context.env.DB.prepare(
    "SELECT subject FROM oauth_identities WHERE provider = ? AND user_id = ?",
  ).bind(provider, userId).first<{ subject: string }>();
  if (existing && existing.subject !== identity.subject) return false;
  await context.env.DB.prepare(
    `INSERT INTO oauth_identities (provider, subject, user_id, email, linked_at) VALUES (?, ?, ?, ?, ?)
     ON CONFLICT(provider, subject) DO UPDATE SET email = excluded.email`,
  ).bind(provider, identity.subject, userId, identity.email, epochSeconds()).run();
  return true;
}

async function callback(context: RequestContext, providerName: string): Promise<Response> {
  const provider = providerConfig(context.env, providerName);
  if (!provider) return redirect("/login?oauth_error=not_configured", [stateCookie("", 0)]);
  const url = new URL(context.request.url);
  if (url.searchParams.get("error")) return redirect("/login?oauth_error=cancelled", [stateCookie("", 0)]);
  const state = await consumeState(context, provider.name, url.searchParams.get("state") || "");
  if (!state) return redirect("/login?oauth_error=state", [stateCookie("", 0)]);
  try {
    const accessToken = await exchangeCode(context, provider, url.searchParams.get("code") || "", state);
    const identity = await fetchIdentity(provider, accessToken);
    if (state.action === "link") {
      if (!state.user_id || !(await linkIdentity(context, provider.name, state.user_id, identity))) {
        return redirect("/?oauth_error=identity_in_use", [stateCookie("", 0)]);
      }
      await audit(context.env, state.user_id, "oauth_linked", "ok", `provider=${provider.name}; token omitted`);
      return redirect("/?oauth_success=linked", [stateCookie("", 0)]);
    }
    const user = await context.env.DB.prepare(
      `SELECT users.id, users.username, users.role, users.mfa_secret_encrypted
         FROM oauth_identities JOIN users ON users.id = oauth_identities.user_id
        WHERE oauth_identities.provider = ? AND oauth_identities.subject = ? AND users.disabled_at IS NULL`,
    ).bind(provider.name, identity.subject).first<{ id: string; username: string; role: "admin" | "user"; mfa_secret_encrypted: string | null }>();
    if (!user) return redirect("/login?oauth_error=not_linked", [stateCookie("", 0)]);
    if (user.mfa_secret_encrypted) {
      const challenge = randomToken(32);
      const now = epochSeconds();
      await context.env.DB.prepare(
        "INSERT INTO oauth_mfa_challenges (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
      ).bind(await sha256(challenge), user.id, now, now + STATE_TTL).run();
      await audit(context.env, user.id, "oauth_login", "mfa_required", `provider=${provider.name}; token omitted`);
      return redirect("/login?oauth_mfa=required", [stateCookie("", 0), mfaCookie(challenge)]);
    }
    const session = await createSession(context.env, user.id, context.request.headers.get("User-Agent") || "OAuth browser");
    await audit(context.env, user.id, "oauth_login", "ok", `provider=${provider.name}; token omitted`);
    return redirect("/?oauth_success=login", [stateCookie("", 0), sessionCookie(session.token, session.maxAge)]);
  } catch {
    await audit(context.env, state.user_id, "oauth_callback", "failed", `provider=${provider.name}; provider error omitted`);
    return redirect(state.action === "link" ? "/?oauth_error=failed" : "/login?oauth_error=failed", [stateCookie("", 0)]);
  }
}

async function completeMfa(context: RequestContext): Promise<Response> {
  const challenge = parseCookies(context.request)[MFA_COOKIE] || "";
  if (!challenge) return errorJson("คำขอยืนยัน Social Login หมดอายุ", 401);
  const payload = await readJson<{ code?: string }>(context.request, 8_000);
  const tokenHash = await sha256(challenge);
  const row = await context.env.DB.prepare(
    `SELECT users.id, users.username, users.role, users.mfa_secret_encrypted, users.mfa_recovery_hashes_json,
            oauth_mfa_challenges.failed_attempts, oauth_mfa_challenges.expires_at
       FROM oauth_mfa_challenges JOIN users ON users.id = oauth_mfa_challenges.user_id
      WHERE oauth_mfa_challenges.token_hash = ? AND users.disabled_at IS NULL`,
  ).bind(tokenHash).first<{
    id: string; username: string; role: "admin" | "user"; mfa_secret_encrypted: string | null;
    mfa_recovery_hashes_json: string; failed_attempts: number; expires_at: number;
  }>();
  if (!row || row.expires_at <= epochSeconds() || row.failed_attempts >= 5 || !row.mfa_secret_encrypted) {
    await context.env.DB.prepare("DELETE FROM oauth_mfa_challenges WHERE token_hash = ?").bind(tokenHash).run();
    return errorJson("คำขอยืนยัน Social Login หมดอายุ", 401);
  }
  const code = String(payload.code || "").trim();
  let valid = false;
  try { valid = await verifyTotp(await decryptSecret(context.env, row.mfa_secret_encrypted), code); } catch { valid = false; }
  if (!valid) {
    const recovery = await consumeRecoveryCode(row.mfa_recovery_hashes_json || "[]", code);
    valid = recovery.ok;
    if (valid) await context.env.DB.prepare("UPDATE users SET mfa_recovery_hashes_json = ? WHERE id = ?").bind(JSON.stringify(recovery.remaining), row.id).run();
  }
  if (!valid) {
    await context.env.DB.prepare("UPDATE oauth_mfa_challenges SET failed_attempts = failed_attempts + 1 WHERE token_hash = ?").bind(tokenHash).run();
    await audit(context.env, row.id, "oauth_login_mfa", "failed", "Invalid MFA code");
    return errorJson("รหัส MFA หรือรหัสกู้คืนไม่ถูกต้อง", 401);
  }
  await context.env.DB.prepare("DELETE FROM oauth_mfa_challenges WHERE token_hash = ?").bind(tokenHash).run();
  const session = await createSession(context.env, row.id, context.request.headers.get("User-Agent") || "OAuth browser");
  await audit(context.env, row.id, "oauth_login_mfa", "ok", "OAuth MFA completed");
  return jsonWithCookies(
    { id: row.id, username: row.username, role: row.role },
    200,
    [sessionCookie(session.token, session.maxAge), mfaCookie("", 0)],
  );
}

async function unlink(context: RequestContext, providerName: string): Promise<Response> {
  if (!context.user) return errorJson("ต้องเข้าสู่ระบบ", 401);
  if (providerName !== "google" && providerName !== "github") return errorJson("ไม่รู้จักผู้ให้บริการ", 404);
  const result = await context.env.DB.prepare(
    "DELETE FROM oauth_identities WHERE provider = ? AND user_id = ?",
  ).bind(providerName, context.user.id).run();
  await audit(context.env, context.user.id, "oauth_unlinked", "ok", `provider=${providerName}`);
  return json({ unlinked: Number(result.meta.changes || 0) > 0 });
}

export async function handleOAuth(context: RequestContext, path: string): Promise<Response | null> {
  if (path === "/api/auth/oauth/providers" && context.request.method === "GET") return providerStatus(context);
  if (path === "/api/auth/oauth/mfa/complete" && context.request.method === "POST") return completeMfa(context);
  const start = path.match(/^\/api\/auth\/oauth\/(google|github)\/start$/);
  if (start && context.request.method === "GET") return begin(context, start[1], "login");
  const link = path.match(/^\/api\/auth\/oauth\/(google|github)\/link\/start$/);
  if (link && context.request.method === "POST") return begin(context, link[1], "link");
  const callbackMatch = path.match(/^\/api\/auth\/oauth\/(google|github)\/callback$/);
  if (callbackMatch && context.request.method === "GET") return callback(context, callbackMatch[1]);
  const unlinkMatch = path.match(/^\/api\/auth\/oauth\/(google|github)$/);
  if (unlinkMatch && context.request.method === "DELETE") return unlink(context, unlinkMatch[1]);
  return null;
}
