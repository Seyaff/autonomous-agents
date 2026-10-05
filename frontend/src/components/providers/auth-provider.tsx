"use client"

import {
    createContext,
    useContext,
    useMemo,
    useEffect,
} from "react"
import { useRouter, usePathname } from "next/navigation"
import { useQueryClient } from "@tanstack/react-query"

import API from "@/lib/axios-client"
import { useGetCurrentUser } from "@/hooks/auth/get-me"
import { useSetupState } from "@/hooks/setup/use-setup-state"
import { isSetupStep, routeIndex } from "@/lib/setup"


export type UserRole = "FOUNDER" | "OWNER"

export interface User {
    _id: string
    user_id: string
    full_name: string
    email: string
    role: UserRole
    is_onboarded: boolean
    active_tenant_id: string
    tenants: string[]
    created_at: string
    updated_at: string
    last_login: string
}

interface AuthContextValue {
    user: User | null
    isLoading: boolean
    isAuthenticated: boolean
    isFounder: boolean
    isOnboarded: boolean
    activeTenantId: string | null
    tenants: string[]
    error: Error | null
    refetch: () => void
    logout: () => void
    switchTenant: (tenantId: string) => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

const PUBLIC_PATHS = ["/", "/login", "/signup", "/privacy", "/terms", "/pricing", "/how-it-works", "/faq", "/guides"]
// Public sections with sub-pages, such as /guides/<slug>. Matched by prefix.
const PUBLIC_PREFIXES = ["/guides/", "/features/", "/compare/"]
const STAFF_PREFIX = "/staff/"

// The restaurant's name on a linked iPad. The server sets it next to the iPad's link.
function readIpadSlug(): string | null {
    if (typeof document === "undefined") return null
    const match = document.cookie.match(/(?:^|;\s*)siyaf_ipad=([^;]+)/)
    return match ? decodeURIComponent(match[1]) : null
}
const FOUNDER_PREFIX = "/founder"
const SETUP_PREFIX = "/setup"

// Before the restaurant exists, the owner can only be on these two steps.
const BEFORE_RESTAURANT_PATHS = ["/setup/welcome", "/setup/restaurant"]
// Once setup is finished, these skipped optional steps stay reachable.
const DISMISSIBLE_AFTER_SETUP = ["/setup/menu", "/setup/whatsapp"]

function isSetupPath(pathname: string) {
    return pathname === SETUP_PREFIX || pathname.startsWith(`${SETUP_PREFIX}/`)
}

function stepOf(pathname: string) {
    return pathname.split("/")[2] ?? ""
}

export default function AuthProvider({
    children,
}: {
    children: React.ReactNode
}) {
    const router = useRouter()
    const pathname = usePathname()
    const queryClient = useQueryClient()

    const {
        data: user,
        isLoading,
        error,
        refetch,
    } = useGetCurrentUser()

    const isAuthenticated = !!user
    const isFounder = user?.role === "FOUNDER"
    const isOnboarded = !!user?.is_onboarded
    const activeTenantId = user?.active_tenant_id ?? null
    const tenants = user?.tenants ?? []

    // Setup progress comes from the server. Owners without a restaurant have
    // nothing to read yet, so the query stays off for them.
    const setup = useSetupState({
        enabled: isAuthenticated && !isFounder && !!activeTenantId,
    })

    // Handle redirects based on auth/role/setup state
    useEffect(() => {
        // A linked restaurant iPad is locked to its staff screen. Nothing else on it is reachable.
        const ipadSlug = readIpadSlug()
        if (ipadSlug && !pathname.startsWith(STAFF_PREFIX)) {
            router.replace(`${STAFF_PREFIX}${ipadSlug}`)
            return
        }

        if (isLoading) return

        // Staff screens run on their own PIN sign-in, so the owner's session never moves them.
        if (pathname.startsWith(STAFF_PREFIX)) return

        const isPublicPath = PUBLIC_PATHS.some(p => pathname === p)
            || PUBLIC_PREFIXES.some(p => pathname.startsWith(p))
        const isFounderPath = pathname.startsWith(FOUNDER_PREFIX)

        // Not authenticated -> redirect to login (unless on public path)
        if (!isAuthenticated) {
            if (!isPublicPath) router.replace("/login")
            return
        }

        // FOUNDER has its own surface. Anything outside /founder bounces back there.
        if (isFounder) {
            if (!isFounderPath) router.replace("/founder")
            return
        }

        // Owner, no restaurant yet: only the first two steps are reachable.
        if (!activeTenantId) {
            if (!BEFORE_RESTAURANT_PATHS.includes(pathname)) router.replace("/setup/welcome")
            return
        }

        // Owner with a restaurant: wait for the setup state before deciding.
        if (setup.isLoading || setup.isError) return

        if (!setup.isComplete) {
            // Setup in progress: stay on the current step, or go back to any earlier one.
            if (!isSetupPath(pathname)) {
                router.replace(`${SETUP_PREFIX}/${setup.currentStep}`)
                return
            }
            const step = stepOf(pathname)
            if (step && routeIndex(step) > routeIndex(setup.currentStep)) {
                router.replace(`${SETUP_PREFIX}/${setup.currentStep}`)
            }
            return
        }

        // Setup finished: setup pages are closed, except skipped optional steps.
        if (isSetupPath(pathname)) {
            const step = stepOf(pathname)
            const skippedStillReachable =
                DISMISSIBLE_AFTER_SETUP.includes(pathname) &&
                isSetupStep(step) &&
                setup.skippedSteps.includes(step)
            if (!skippedStillReachable) router.replace("/dashboard")
            return
        }

        if (isPublicPath || pathname === "/") {
            router.replace("/dashboard")
            return
        }

        // Owners never see the founder console
        if (isFounderPath) {
            router.replace("/dashboard")
        }
    }, [
        isAuthenticated,
        isFounder,
        isLoading,
        pathname,
        router,
        activeTenantId,
        setup.isLoading,
        setup.isError,
        setup.isComplete,
        setup.currentStep,
        setup.skippedSteps,
    ])

    // ---------- Actions ----------

    const logout = async () => {
        try {
            await API.post("/auth/logout")
        } catch {
        }
        queryClient.setQueryData(["me"], null)
        queryClient.clear()
        router.replace("/login")
    }

    const switchTenant = async (tenantId: string) => {
        if (!tenantId || tenantId === activeTenantId) return

        await API.post("/auth/switch-tenant", { tenant_id: tenantId })
        await refetch()
        queryClient.invalidateQueries()
    }

    const value = useMemo<AuthContextValue>(
        () => ({
            user: user ?? null,
            isLoading,
            isAuthenticated,
            isFounder,
            isOnboarded,
            activeTenantId,
            tenants,
            error: (error as Error) ?? null,
            refetch,
            logout,
            switchTenant,
        }),
        [
            user,
            isLoading,
            isAuthenticated,
            isFounder,
            isOnboarded,
            activeTenantId,
            tenants,
            error,
            refetch,
        ]
    )

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    )
}

export function useAuth() {
    const ctx = useContext(AuthContext)
    if (!ctx) {
        throw new Error("useAuth must be used within <AuthProvider>")
    }
    return ctx
}