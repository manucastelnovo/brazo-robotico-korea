import { NextResponse, type NextRequest } from "next/server";
import { isSameOrigin } from "@/lib/sameOrigin";
import { SESSION_COOKIE } from "@/lib/session";

export async function POST(request: NextRequest) {
  if (!isSameOrigin(request)) return NextResponse.json({ error: "Cross-site request blocked" }, { status: 403 });
  const response = NextResponse.json({ ok: true });
  response.cookies.delete(SESSION_COOKIE);
  return response;
}
