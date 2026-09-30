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


export type UserRole = "OWNER" | "ADMIN" | "STAFF"

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
    isOnboarded: boolean
    activeTenantId: string | null
    tenants: string[]
    error: Error | null
    refetch: () => void
    logout: () => void
    switchTenant: (tenantId: string) => Promise<void>
    completeOnboarding: (tenantId: string) => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

const ONBOARDING_PATHS = ["/onboarding", "/settings"]
const PUBLIC_PATHS = ["/login", "/signup", "/privacy"]

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
    const isOnboarded = !!user?.is_onboarded
    const activeTenantId = user?.active_tenant_id ?? null
    const tenants = user?.tenants ?? []

    // Handle redirects based on auth/onboarding state
    useEffect(() => {
        if (isLoading) return

        const isOnboardingPath = ONBOARDING_PATHS.some(p => pathname.startsWith(p))
        const isPublicPath = PUBLIC_PATHS.some(p => pathname === p)

        // Not authenticated -> redirect to login (unless on public path)
        if (!isAuthenticated && !isPublicPath) {
            router.replace("/login")
            return
        }

        // Authenticated but not onboarded -> redirect to onboarding (unless already there)
        if (isAuthenticated && !isOnboarded && !isOnboardingPath) {
            router.replace("/onboarding")
            return
        }

        // Authenticated and onboarded but on onboarding path -> redirect to dashboard
        if (isAuthenticated && isOnboarded && isOnboardingPath) {
            router.replace("/dashboard")
            return
        }

        // Authenticated and onboarded but on public path -> redirect to dashboard
        if (isAuthenticated && isOnboarded && isPublicPath) {
            router.replace("/dashboard")
            return
        }
    }, [isAuthenticated, isOnboarded, isLoading, pathname, router])

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

    const completeOnboarding = async (tenantId: string) => {
        await API.post("/auth/complete-onboarding", { tenant_id: tenantId })
        await refetch()
        queryClient.invalidateQueries()
        router.replace("/dashboard")
    }

    const value = useMemo<AuthContextValue>(
        () => ({
            user: user ?? null,
            isLoading,
            isAuthenticated,
            isOnboarded,
            activeTenantId,
            tenants,
            error: (error as Error) ?? null,
            refetch,
            logout,
            switchTenant,
            completeOnboarding,
        }),
        [
            user,
            isLoading,
            isAuthenticated,
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