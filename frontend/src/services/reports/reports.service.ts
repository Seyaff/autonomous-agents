import API from "@/lib/axios-client"

export interface WeeklyReportMetrics {
  period_start: string
  period_end: string
  total_orders: number
  total_revenue: number
  revenue_growth_pct: number
  delivered_orders: number
  cancelled_orders: number
  cancellation_rate: number
  average_order_value: number
  unique_customers: number
  top_items: { name: string; quantity?: number; count?: number }[] | unknown[]
  total_conversations: number
  total_messages: number
}

export interface WeeklyReport {
  _id?: string
  business_name?: string
  metrics: WeeklyReportMetrics
  summary: string
  created_at: string
  delivered_via_whatsapp: boolean
}

export const listWeeklyReports = async (): Promise<WeeklyReport[]> => {
  const res = await API.get("/analytics/weekly-reports")
  return res.data.reports
}

/** Also sends the report to the owner's WhatsApp. */
export const generateWeeklyReport = async (): Promise<WeeklyReport> => {
  const res = await API.post("/analytics/weekly/generate")
  return res.data.report
}
