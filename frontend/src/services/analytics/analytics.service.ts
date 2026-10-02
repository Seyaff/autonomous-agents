import API from "@/lib/axios-client"

export interface SevenDayAnalytics {
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
  top_items: [string, number][]
  total_conversations: number
  total_messages: number
}

export const get7DaySummary = async (): Promise<SevenDayAnalytics> => {
  const res = await API.get("/analytics/7day-summary")
  return res.data.metrics
}
