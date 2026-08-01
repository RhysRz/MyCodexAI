import type { Env } from "./types";
import { base64Url, decodeBase64Url, safeEqual, sha256 } from "./security";

const encoder = new TextEncoder();
const BASE32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";

function ownedBuffer(bytes: Uint8Array): ArrayBuffer {
  const copy = new Uint8Array(bytes.byteLength);
  copy.set(bytes);
  return copy.buffer;
}

function encryptionMaterial(env: Env): string {
  const value = env.AUTH_ENCRYPTION_KEY || "";
  if (value.length < 32) throw new Error("ยังไม่ได้ตั้งค่า secret สำหรับเข้ารหัส MFA");
  return value;
}

async function aesKey(env: Env): Promise<CryptoKey> {
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(encryptionMaterial(env)));
  return crypto.subtle.importKey("raw", digest, "AES-GCM", false, ["encrypt", "decrypt"]);
}

export async function encryptSecret(env: Env, plaintext: string): Promise<string> {
  const iv = new Uint8Array(12);
  crypto.getRandomValues(iv);
  const encrypted = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, await aesKey(env), encoder.encode(plaintext));
  return `${base64Url(iv)}.${base64Url(new Uint8Array(encrypted))}`;
}

export async function decryptSecret(env: Env, value: string): Promise<string> {
  const [iv, ciphertext] = value.split(".");
  if (!iv || !ciphertext) throw new Error("ข้อมูล MFA ไม่ถูกต้อง");
  const plain = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: ownedBuffer(decodeBase64Url(iv)) },
    await aesKey(env),
    ownedBuffer(decodeBase64Url(ciphertext)),
  );
  return new TextDecoder().decode(plain);
}

export function base32Encode(bytes: Uint8Array): string {
  let bits = 0;
  let value = 0;
  let output = "";
  for (const byte of bytes) {
    value = (value << 8) | byte;
    bits += 8;
    while (bits >= 5) {
      output += BASE32[(value >>> (bits - 5)) & 31];
      bits -= 5;
    }
  }
  if (bits > 0) output += BASE32[(value << (5 - bits)) & 31];
  return output;
}

function base32Decode(input: string): Uint8Array {
  let bits = 0;
  let value = 0;
  const output: number[] = [];
  for (const character of input.toUpperCase().replace(/[^A-Z2-7]/g, "")) {
    const index = BASE32.indexOf(character);
    if (index < 0) continue;
    value = (value << 5) | index;
    bits += 5;
    if (bits >= 8) {
      output.push((value >>> (bits - 8)) & 255);
      bits -= 8;
    }
  }
  return Uint8Array.from(output);
}

export function createTotpSecret(): string {
  const bytes = new Uint8Array(20);
  crypto.getRandomValues(bytes);
  return base32Encode(bytes);
}

async function totpAt(secret: string, counter: number): Promise<string> {
  const counterBytes = new Uint8Array(8);
  let remaining = counter;
  for (let index = 7; index >= 0; index -= 1) {
    counterBytes[index] = remaining & 255;
    remaining = Math.floor(remaining / 256);
  }
  const key = await crypto.subtle.importKey("raw", ownedBuffer(base32Decode(secret)), { name: "HMAC", hash: "SHA-1" }, false, ["sign"]);
  const signature = new Uint8Array(await crypto.subtle.sign("HMAC", key, counterBytes));
  const offset = signature[signature.length - 1] & 15;
  const number = ((signature[offset] & 127) << 24) | (signature[offset + 1] << 16) | (signature[offset + 2] << 8) | signature[offset + 3];
  return String(number % 1_000_000).padStart(6, "0");
}

export async function verifyTotp(secret: string, code: string, now = Date.now()): Promise<boolean> {
  const clean = code.replace(/\s/g, "");
  if (!/^\d{6}$/.test(clean)) return false;
  const counter = Math.floor(now / 30_000);
  for (const drift of [-1, 0, 1]) {
    if (await safeEqual(await totpAt(secret, counter + drift), clean)) return true;
  }
  return false;
}

export function createRecoveryCodes(): string[] {
  return Array.from({ length: 10 }, () => {
    const bytes = new Uint8Array(12);
    crypto.getRandomValues(bytes);
    const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
    const compact = Array.from(bytes, (byte) => alphabet[byte & 31]).join("");
    return `${compact.slice(0, 4)}-${compact.slice(4, 8)}-${compact.slice(8, 12)}`;
  });
}

export async function recoveryHashes(codes: string[]): Promise<string[]> {
  return Promise.all(codes.map((code) => sha256(code.toUpperCase().replace(/[^A-Z0-9]/g, ""))));
}

export async function consumeRecoveryCode(storedJson: string, code: string): Promise<{ ok: boolean; remaining: string[] }> {
  let hashes: string[] = [];
  try {
    const parsed = JSON.parse(storedJson) as unknown;
    hashes = Array.isArray(parsed) ? parsed.map(String) : [];
  } catch { hashes = []; }
  const candidate = await sha256(code.toUpperCase().replace(/[^A-Z0-9]/g, ""));
  for (let index = 0; index < hashes.length; index += 1) {
    if (await safeEqual(hashes[index], candidate)) return { ok: true, remaining: hashes.filter((_, itemIndex) => itemIndex !== index) };
  }
  return { ok: false, remaining: hashes };
}
