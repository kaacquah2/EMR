/**
 * Next.js edge middleware — UX-layer route gating only.
 *
 * SECURITY NOTE: The `medsync_role` cookie read below is set client-side and is
 * NOT HttpOnly, so it can be edited by any user in their browser's DevTools.
 * This middleware therefore provides a UX convenience (redirect to /unauthorized
 * before the page renders) but is NOT a security boundary.
 *
 * True authorization is enforced by the Django backend on every API call:
 *   - JWT bearer token verification (SimpleJWT)
 *   - Role/permission check (shared/permissions.py:PermissionEnforcementMiddleware)
 *   - Hospital scoping (api/utils.py get_*_queryset helpers)
 *
 * Do NOT gate data fetches or sensitive actions on client-side role values.
 */
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

export function middleware(request: NextRequest) {
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
