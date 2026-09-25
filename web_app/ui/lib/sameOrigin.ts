import type { NextRequest } from "next/server";

/** Blocks cross-site POSTs to our route handlers (browsers always send Origin on POST). */
export function isSameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  return origin === null || origin === request.nextUrl.origin;
}
