import { NextResponse, type NextRequest } from "next/server";
import { isValidSession, SESSION_COOKIE } from "@/lib/session";

/** Protects /control and skips /login for users who already have a valid session. Runs on Node.js. */
export function proxy(request: NextRequest) {
  const loggedIn = isValidSession(request.cookies.get(SESSION_COOKIE)?.value);
  const { pathname } = request.nextUrl;

  if (pathname.startsWith("/control") && !loggedIn) {
    const response = NextResponse.redirect(new URL("/login", request.url));
    response.cookies.delete(SESSION_COOKIE); // drop an expired or forged cookie
    return response;
  }
  if (pathname === "/login" && loggedIn) {
    return NextResponse.redirect(new URL("/control", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/control/:path*", "/login"],
};
