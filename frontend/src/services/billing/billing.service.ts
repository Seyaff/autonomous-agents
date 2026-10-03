import API from "@/lib/axios-client"

export interface UsageResponse {
  plan_key: string
  plan_name: string
  period: string
  used: number
  limit: number
  ai_messages: number
  tokens_used: number
}

export const getUsage = async (): Promise<UsageResponse> => {
  const res = await API.get("/billing/usage")
  return res.data
}
