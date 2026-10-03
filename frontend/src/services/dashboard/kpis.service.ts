import API from "@/lib/axios-client"

export type KpiRange = "today" | "7d"

export interface DashboardKpis {
  range: KpiRange
  currency: string
  orders: number
  revenue: number
  conversations: number
  ai_handled_pct: number
  median_first_reply_s: number | null
  needs_you: number
}

export const getDashboardKpis = async (range: KpiRange): Promise<DashboardKpis> => {
  const res = await API.get("/dashboard/kpis", { params: { range } })
  return res.data
}
