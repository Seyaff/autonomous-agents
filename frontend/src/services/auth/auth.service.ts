import API from "@/lib/axios-client"

export interface User {
    _id: string
    user_id: string
    full_name: string
    email: string
    role: "FOUNDER" | "OWNER"
    is_onboarded: boolean
    active_tenant_id: string
    tenants: string[]
    created_at: string
    updated_at: string
    last_login: string
}

export const getUserQuery = async (): Promise<User | null> => {
    try {
        const response = await API.get<User>("/auth/me")
        return response.data
    } catch (error: any) {
        if (error.response?.status === 401) {
            return null
        }
        throw error
    }
}

export const signupUser = async (email: string, password: string, fullName: string) => {
    const response = await API.post("/auth/signup", { email, password, full_name: fullName })
    return response.data
}

export const loginUser = async (email: string, password: string) => {
    const response = await API.post("/auth/login", { email, password })
    return response.data
}

export const logoutUser = async () => {
    await API.post("/auth/logout")
}

export const switchTenant = async (tenantId: string) => {
    const response = await API.post("/auth/switch-tenant", { tenant_id: tenantId })
    return response.data
}