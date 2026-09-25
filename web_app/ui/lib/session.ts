/**
 * Session tokens issued by the Python bridge (web_app/bridge/tokens.py).
 *
 * Format: base64url(json payload) + "." + base64url(HMAC-SHA256(secret, first part)).
 * The HMAC key is the secret string itself (UTF-8), exactly like the bridge.
 * Server only: it reads the shared secret file with node:fs.
 */
import { createHmac, timingSafeEqual } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";

export const SESSION_COOKIE = "huenit_session";
const SUBJECT = "face-1";
const BASE64URL = /^[A-Za-z0-9_-]+$/;

export type SessionPayload = { sub: string; exp: number; jti: string };

export class MissingSecretError extends Error {}

/** Default location: web_app/.session_secret, one level above the ui folder. */
export function secretFilePath(cwd: string = process.cwd()): string {
  return path.resolve(cwd, "..", ".session_secret");
}

/**
 * Same rule as secret.py: $HUENIT_SESSION_SECRET wins, else the shared file.
 * Never creates the file: the bridge owns it. Fails closed when it is missing.
 */
export function loadSecret(file: string = secretFilePath()): string {
  const fromEnv = process.env.HUENIT_SESSION_SECRET?.trim();
  if (fromEnv) return fromEnv;
  let value = "";
  try {
    value = readFileSync(file, "ascii").trim();
  } catch {
    // handled below
  }
  if (!value) {
    throw new MissingSecretError(
      `Session secret not found at ${file}. Start the bridge first (python -m web_app.bridge); it creates the file.`,
    );
  }
  return value;
}

/** Returns the payload when the token is authentic and not expired, else null. */
export function verifySessionToken(
  token: string | undefined | null,
  secret: string,
  now: number = Date.now() / 1000,
): SessionPayload | null {
  if (!token) return null;
  const parts = token.split(".");
  if (parts.length !== 2) return null;
  const [body, signature] = parts;
  if (!BASE64URL.test(body) || !BASE64URL.test(signature)) return null;

  const expected = createHmac("sha256", secret).update(body, "ascii").digest();
  const received = Buffer.from(signature, "base64url");
  if (received.length !== expected.length || !timingSafeEqual(received, expected)) return null;

  let payload: unknown;
  try {
    payload = JSON.parse(Buffer.from(body, "base64url").toString("utf8"));
  } catch {
    return null;
  }
  if (typeof payload !== "object" || payload === null) return null;
  const { sub, exp, jti } = payload as Record<string, unknown>;
  if (sub !== SUBJECT || typeof exp !== "number" || !Number.isInteger(exp) || exp <= now) return null;
  return { sub, exp, jti: String(jti ?? "") };
}

/** Convenience for server code: false when the secret is missing (fail closed). */
export function isValidSession(token: string | undefined | null): boolean {
  try {
    return verifySessionToken(token, loadSecret()) !== null;
  } catch (error) {
    if (error instanceof MissingSecretError) {
      console.error(error.message);
      return false;
    }
    throw error;
  }
}
