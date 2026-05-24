import { NextResponse, type NextRequest } from "next/server";
import { isPathnameAccessible } from "./lib/navigation";

const AUTH_ROUTES = ["/login", "/activate", "/forgot-password", "/reset-password"];

function isPublicRoute(pathname: string): boolean {
  return (
    pathname.startsWith("/auth") ||
    pathname === "/unauthorized" ||
    AUTH_ROUTES.some((route) => pathname === route || pathname.startsWith(`${route}/`)) ||
    pathname.startsWith("/_next") ||
    pathname.includes(".") ||
    pathname === "/favicon.ico"
  );
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = request.cookies.has("medsync_session");

  if (pathname === "/login" && hasSession) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  if (isPublicRoute(pathname)) {
    return NextResponse.next();
  }

  if (!hasSession) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  const userRole = request.cookies.get("medsync_role")?.value;
  if (!userRole) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (!isPathnameAccessible(userRole, pathname)) {
    return NextResponse.redirect(new URL("/unauthorized", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
