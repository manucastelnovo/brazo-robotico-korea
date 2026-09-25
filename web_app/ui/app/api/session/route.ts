import { NextResponse, type NextRequest } from "next/server";
import { BRIDGE_INTERNAL_URL } from "@/lib/bridge";
import { isSameOrigin } from "@/lib/sameOrigin";
import { loadSecret, MissingSecretError, SESSION_COOKIE, verifySessionToken } from "@/lib/session";

const GRANT_PATTERN = /^[A-Za-z0-9_-]{16,128}$/;
const BRIDGE_TIMEOUT_MS = 5000;

function fail(status: number, error: string) {
  return NextResponse.json({ error }, { status });
}

/** Trades the one-time grant from the bridge for an httpOnly session cookie. */
export async function POST(request: NextRequest) {
  if (!isSameOrigin(request)) return fail(403, "Cross-site request blocked");

  const body: unknown = await request.json().catch(() => null);
  const grant = (body as { grant?: unknown } | null)?.grant;
  if (typeof grant !== "string" || !GRANT_PATTERN.test(grant)) return fail(400, "Invalid grant");

  let redeemed: Response;
  try {
    redeemed = await fetch(`${BRIDGE_INTERNAL_URL}/auth/redeem`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ grant }),
      cache: "no-store",
      signal: AbortSignal.timeout(BRIDGE_TIMEOUT_MS),
    });
  } catch {
    return fail(502, "Bridge unreachable");
  }
  if (redeemed.status === 401) return fail(401, "Grant invalid or expired");
  if (!redeemed.ok) return fail(502, `Bridge error ${redeemed.status}`);

  const { token } = (await redeemed.json().catch(() => ({}))) as { token?: unknown };
  let payload;
  try {
    payload = typeof token === "string" ? verifySessionToken(token, loadSecret()) : null;
  } catch (error) {
    if (error instanceof MissingSecretError) return fail(500, error.message);
    throw error;
  }
  if (!payload) return fail(401, "Bridge returned an invalid token");

  const response = NextResponse.json({ ok: true });
  response.cookies.set({
    name: SESSION_COOKIE,
    value: token as string,
    httpOnly: true,
    sameSite: "strict",
    secure: false, // plain http on localhost: this is a local demo
    path: "/",
    maxAge: Math.max(0, Math.floor(payload.exp - Date.now() / 1000)),
  });
  return response;
}
