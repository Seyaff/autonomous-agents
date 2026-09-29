import API from "@/lib/axios-client"

export interface TenantContext {
    tenant_id: string
    user_id: string
    role: string
}

export interface QueryAgentPayload {
    query: string
    tenant_id: string
    tenant: TenantContext
    customer_phone: string
    user_message: string
}

export interface AgentResponse {
    success: boolean
    response: string
    intent: string | null
    actions: Record<string, unknown>[]
    metadata: Record<string, unknown>
}

export const queryAgentMutationFn = async (
    payload: QueryAgentPayload
): Promise<AgentResponse> => {
    const response = await API.post<AgentResponse>("/agent/query", payload)
    return response.data
}