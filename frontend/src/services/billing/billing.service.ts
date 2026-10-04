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
  pending_plan: string | null
  pending_plan_name: string | null
  next_invoice_date: string | null
  next_invoice_pkr: number
  meta_fee_pkr: number
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

export interface InvoiceLine {
  description: string
  quantity: number
  amount_pkr: number
}

export interface Invoice {
  invoice_id: string
  tenant_id: string
  purpose: string
  plan_key: string
  interval: "month" | "year"
  period_start: string
  period_end: string
  lines: InvoiceLine[]
  amount_pkr: number
  status: "open" | "paid" | "void"
  due_at: string
  paid_at: string | null
  provider: string | null
  payment_reference: string | null
  created_at: string
}

export interface PaymentResponse {
  redirect_url?: string
  invoice: Invoice | null
  subscription: Partial<SubscriptionResponse> & { status?: string; current_period_end?: string | null }
}

export const checkout = async (plan: string, interval: "month" | "year"): Promise<PaymentResponse> => {
  const res = await API.post("/billing/checkout", { plan, interval })
  return res.data
}

export const payInvoice = async (invoiceId: string): Promise<PaymentResponse> => {
  const res = await API.post(`/billing/invoices/${encodeURIComponent(invoiceId)}/pay`, { method: "card" })
  return res.data
}

export const getInvoices = async (): Promise<Invoice[]> => {
  const res = await API.get("/billing/invoices")
  return res.data
}

export const changePlan = async (plan: string): Promise<PaymentResponse> => {
  const res = await API.post("/billing/change-plan", { plan })
  return res.data
}

export const cancelSubscription = async (): Promise<{ subscription: SubscriptionResponse }> => {
  const res = await API.post("/billing/cancel")
  return res.data
}

export const resumeSubscription = async (): Promise<{ subscription: SubscriptionResponse }> => {
  const res = await API.post("/billing/resume")
  return res.data
}
