import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

// ---------- Route config ----------

const PUBLIC_ROUTES = ["/login", "/register", "/forgot-password"]
const AUTH_ROUTES = ["/login", "/register"  ,"/dashboard"]
const ONBOARDING_ROUTE = "/onboarding"

const AUTH_COOKIE = "access_token"

export function proxy(request: NextRequest) {
    const { pathname } = request.nextUrl

    const token = request.cookies.get(AUTH_COOKIE)?.value
    const isAuthenticated = !!token

    const isPublicRoute = PUBLIC_ROUTES.some((r) => pathname.startsWith(r))
    const isAuthRoute = AUTH_ROUTES.includes(pathname)
    const isOnboardingRoute = pathname === ONBOARDING_ROUTE

    if (!isAuthenticated && !isPublicRoute) {
        const url = request.nextUrl.clone()
        url.pathname = "/login"
        url.searchParams.set("next", pathname)
        return NextResponse.redirect(url)
    }
    if (isAuthenticated && isAuthRoute) {
        return NextResponse.redirect(new URL("/", request.url))
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