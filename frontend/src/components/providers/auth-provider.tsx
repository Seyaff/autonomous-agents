"use client"

import {
    createContext,
    useContext,
    useMemo,
} from "react"
import { useRouter } from "next/navigation"
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
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export default function AuthProvider({
    children,
}: {
    children: React.ReactNode
}) {
    const router = useRouter()
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

// ---------- Hook ----------

export function useAuth() {
    const ctx = useContext(AuthContext)
    if (!ctx) {
        throw new Error("useAuth must be used within <AuthProvider>")
    }
    return ctx
}