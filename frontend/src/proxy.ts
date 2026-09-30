import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

// ---------- Route config ----------

const PUBLIC_ROUTES = ["/login", "/register" , "/signup", "/forgot-password"]
const GUEST_ONLY_ROUTES = ["/login", "/register", "/forgot-password"] // logged-in users get bounced away
const ONBOARDING_ROUTE = "/onboarding"
const AUTH_COOKIE = "access_token"

export function proxy(request: NextRequest) {
    const { pathname } = request.nextUrl
    const token = request.cookies.get(AUTH_COOKIE)?.value
    const isAuthenticated = !!token

    const isPublicRoute = PUBLIC_ROUTES.some((r) => pathname.startsWith(r))
    const isGuestOnlyRoute = GUEST_ONLY_ROUTES.some((r) => pathname.startsWith(r))

    // 1. Not logged in, trying to access a protected route → /login
    if (!isAuthenticated && !isPublicRoute) {
        const url = request.nextUrl.clone()
        url.pathname = "/login"
        url.searchParams.set("next", pathname)
        return NextResponse.redirect(url)
    }

    // 2. Logged in, trying to visit login/register → send to dashboard
    if (isAuthenticated && isGuestOnlyRoute) {
        return NextResponse.redirect(new URL("/dashboard", request.url))
    }

    return NextResponse.next()
}

// ---------- Matcher ----------

export const config = {
    matcher: [
        /*
         * Match all request paths except:
         * - _next/static (static files)
         * - _next/image (image optimization)
         * - favicon.ico
         * - public assets (images, svg, etc.)
         */
        "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
    ],
}