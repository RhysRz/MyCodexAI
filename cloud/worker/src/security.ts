import type { CloudUser, Env } from "./types";

export const SESSION_COOKIE = "__Host-mycodexai_cloud";
// Cloudflare Workers currently reject PBKDF2 iteration counts above 100,000.
// Keep this at the platform maximum so password hashing remains as strong as
// the runtime permits without breaking account bootstrap or login.
const PASSWORD_ITERATIONS = 100_000;
const encoder = new TextEncoder();

export function epochSeconds(): number {
  return Math.floor(Date.now() / 1000);
}

export function base64Url(bytes: Uint8Array): string {
  let binary = "";
  for (let index = 0; index < bytes.length; index += 1) binary += String.fromCharCode(bytes[index]);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

export function decodeBase64Url(value: string): Uint8Array {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
  const binary = atob(padded);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

export function randomToken(byteLength = 32): string {
  const bytes = new Uint8Array(byteLength);
  crypto.getRandomValues(bytes);
  return base64Url(bytes);
}

export async function sha256(value: string | Uint8Array): Promise<string> {
  const input = typeof value === "string" ? encoder.encode(value) : value;
  const bytes = Uint8Array.from(input);
  return base64Url(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes.buffer)));
}

export async function safeEqual(left: string, right: string): Promise<boolean> {
  const [leftHash, rightHash] = await Promise.all([sha256(left), sha256(right)]);
  if (leftHash.length !== rightHash.length) return false;
  let difference = 0;
  for (let index = 0; index < leftHash.length; index += 1) {
    difference |= leftHash.charCodeAt(index) ^ rightHash.charCodeAt(index);
  }
  return difference === 0;
}

async function derivePassword(password: string, salt: Uint8Array, iterations: number): Promise<string> {
  const material = await crypto.subtle.importKey("raw", encoder.encode(password), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", hash: "SHA-256", salt: Uint8Array.from(salt).buffer, iterations },
    material,
    256,
  );
  return base64Url(new Uint8Array(bits));
}

export async function hashPassword(password: string): Promise<string> {
  if (password.length < 12 || password.length > 1_024) throw new Error("รหัสผ่านต้องมีอย่างน้อย 12 ตัวอักษร");
  const salt = new Uint8Array(16);
  crypto.getRandomValues(salt);
  const digest = await derivePassword(password, salt, PASSWORD_ITERATIONS);
  return `pbkdf2-sha256$${PASSWORD_ITERATIONS}$${base64Url(salt)}$${digest}`;
}

export async function verifyPassword(stored: string, password: string): Promise<boolean> {
  const parts = stored.split("$");
  if (parts.length !== 4 || parts[0] !== "pbkdf2-sha256") return false;
  const iterations = Number.parseInt(parts[1], 10);
  if (!Number.isFinite(iterations) || iterations < 50_000 || iterations > 1_000_000) return false;
  try {
    const candidate = await derivePassword(password, decodeBase64Url(parts[2]), iterations);
    return safeEqual(candidate, parts[3]);
  } catch {
    return false;
  }
}

export function parseCookies(request: Request): Record<string, string> {
  const result: Record<string, string> = {};
  for (const item of (request.headers.get("Cookie") || "").split(";")) {
    const separator = item.indexOf("=");
    if (separator <= 0) continue;
    result[item.slice(0, separator).trim()] = decodeURIComponent(item.slice(separator + 1).trim());
  }
  return result;
}

export function sessionCookie(token: string, maxAge: number): string {
  return `${SESSION_COOKIE}=${encodeURIComponent(token)}; Path=/; Max-Age=${maxAge}; Secure; HttpOnly; SameSite=Strict`;
}

export function clearSessionCookie(): string {
  return `${SESSION_COOKIE}=; Path=/; Max-Age=0; Secure; HttpOnly; SameSite=Strict`;
}

export async function currentUser(request: Request, env: Env): Promise<CloudUser | null> {
  const token = parseCookies(request)[SESSION_COOKIE];
  if (!token) return null;
  const now = epochSeconds();
  const tokenHash = await sha256(token);
  const row = await env.DB.prepare(
    `SELECT users.id, users.username, users.role, sessions.last_seen_at
       FROM sessions JOIN users ON users.id = sessions.user_id
      WHERE sessions.token_hash = ? AND sessions.expires_at > ? AND users.disabled_at IS NULL`,
  ).bind(tokenHash, now).first<{ id: string; username: string; role: "admin" | "user"; last_seen_at: number }>();
  if (!row) return null;
  if (now - Number(row.last_seen_at) > 300) {
    await env.DB.prepare("UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?").bind(now, tokenHash).run();
  }
  return { id: row.id, username: row.username, role: row.role };
}

export async function createSession(env: Env, userId: string, deviceLabel: string): Promise<{ token: string; maxAge: number }> {
  const token = randomToken(32);
  const tokenHash = await sha256(token);
  const now = epochSeconds();
  const hours = Math.min(72, Math.max(1, Number.parseInt(env.SESSION_HOURS || "24", 10) || 24));
  const maxAge = hours * 60 * 60;
  await env.DB.batch([
    env.DB.prepare("DELETE FROM sessions WHERE expires_at <= ?").bind(now),
    env.DB.prepare(
      "INSERT INTO sessions (token_hash, user_id, created_at, last_seen_at, expires_at, device_label) VALUES (?, ?, ?, ?, ?, ?)",
    ).bind(tokenHash, userId, now, now, now + maxAge, deviceLabel.slice(0, 120) || "Cloud browser"),
  ]);
  const stale = await env.DB.prepare(
    "SELECT token_hash FROM sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT -1 OFFSET 2",
  ).bind(userId).all<{ token_hash: string }>();
  for (const session of stale.results || []) {
    await env.DB.prepare("DELETE FROM sessions WHERE token_hash = ?").bind(session.token_hash).run();
  }
  return { token, maxAge };
}

export async function clientKey(request: Request, username: string): Promise<string> {
  const address = request.headers.get("CF-Connecting-IP") || "unknown";
  return sha256(`${address}|${username.trim().toLocaleLowerCase()}`);
}

export function sameOrigin(request: Request): boolean {
  if (["GET", "HEAD", "OPTIONS"].includes(request.method.toUpperCase())) return true;
  const origin = request.headers.get("Origin");
  if (!origin) return !parseCookies(request)[SESSION_COOKIE];
  try {
    return new URL(origin).origin === new URL(request.url).origin;
  } catch {
    return false;
  }
}

export async function readJson<T>(request: Request, maximumBytes = 256_000): Promise<T> {
  const declared = Number.parseInt(request.headers.get("Content-Length") || "0", 10);
  if (declared > maximumBytes) throw new Error("ข้อมูลคำขอมีขนาดใหญ่เกินไป");
  const text = await request.text();
  if (encoder.encode(text).byteLength > maximumBytes) throw new Error("ข้อมูลคำขอมีขนาดใหญ่เกินไป");
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new Error("รูปแบบข้อมูลไม่ถูกต้อง");
  }
}

export function json(data: unknown, status = 200, extraHeaders: HeadersInit = {}): Response {
  const headers = new Headers(extraHeaders);
  headers.set("Content-Type", "application/json; charset=utf-8");
  headers.set("Cache-Control", "no-store");
  return secure(new Response(JSON.stringify(data), { status, headers }));
}

export function errorJson(detail: string, status = 400): Response {
  return json({ detail }, status);
}

export function secure(response: Response): Response {
  const headers = new Headers(response.headers);
  headers.set("Content-Security-Policy", "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'");
  headers.set("Cross-Origin-Opener-Policy", "same-origin");
  headers.set("Cross-Origin-Resource-Policy", "same-origin");
  headers.set("Permissions-Policy", "camera=(), geolocation=(), payment=(), usb=(); microphone=(self)");
  headers.set("Referrer-Policy", "no-referrer");
  headers.set("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload");
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("X-Frame-Options", "DENY");
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

export async function audit(env: Env, userId: string | null, kind: string, outcome: string, detail: string): Promise<void> {
  await env.DB.prepare(
    "INSERT INTO audit_events (id, user_id, kind, outcome, detail, created_at) VALUES (?, ?, ?, ?, ?, ?)",
  ).bind(crypto.randomUUID(), userId, kind.slice(0, 80), outcome.slice(0, 30), detail.slice(0, 500), epochSeconds()).run();
}
