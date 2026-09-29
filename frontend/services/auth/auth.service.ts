import { User } from "@/components/providers/auth-provider"
import API from "@/lib/axios-client"


export const getUserQuery = async (): Promise<User> => {
    const response = await API.get<User>("/user/me")
    return response.data
}

export const loginMutation = async (payload: {
    email: string
    password: string
}): Promise<User> => {
    const response = await API.post<User>("/auth/login", payload)
    return response.data
}

export const registerMutation = async (payload: {
    full_name: string
    email: string
    password: string
}): Promise<User> => {
    const response = await API.post<User>("/auth/register", payload)
    return response.data
}

export const logoutMutation = async (): Promise<void> => {
    await API.post("/auth/logout")
}

export const switchTenantMutation = async (
    tenantId: string
): Promise<User> => {
    const response = await API.post<User>("/auth/switch-tenant", {
        tenant_id: tenantId,
    })
    return response.data
}