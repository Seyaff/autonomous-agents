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

export interface SubscriptionResponse {
  plan: string
  plan_name: string
  interval: "month" | "year"
  status: "trialing" | "active" | "past_due" | "paused" | "canceled"
  trial_ends_at: string | null
  trial_days_left: number | null
  current_period_start: string | null
  current_period_end: string | null
  cancel_at_period_end: boolean
  price_pkr: number
  included_chats: number
  extra_chat_pkr: number
  usage: UsageResponse
}

export interface PlanOption {
  key: string
  name: string
  price_monthly_pkr: number
  price_yearly_pkr: number
  ai_conversations_per_month: number
  extra_chat_pkr: number
}

export const getSubscription = async (): Promise<SubscriptionResponse> => {
  const res = await API.get("/billing/subscription")
  return res.data
}

export const getPlans = async (): Promise<PlanOption[]> => {
  const res = await API.get("/billing/plans")
  return res.data
}
