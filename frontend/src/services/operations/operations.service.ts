import API from "@/lib/axios-client"

export type RestaurantHealth = "healthy" | "needs_attention" | "setting_up"

export interface OperatedRestaurant {
  tenant_id: string
  business_name: string
  country: string | null
  owner_email: string | null
  owner_name: string | null
  health: RestaurantHealth
  setup_complete: boolean
  whatsapp_status: "connected" | "shared_number" | "error"
  whatsapp_error: string | null
  display_phone_number: string | null
  agent_enabled: boolean
  last_customer_activity: string | null
  messages_today: number
  orders_today: number
  failed_messages_24h: number
  escalations_open: number
  alerts_unread: number
  alerts_critical: number
  ai_conversations_this_month: number
  plan_limit: number
}

export interface OperatedAlert {
  id: string
  tenant_id: string
  business_name: string
  kind: string
  severity: "info" | "warning" | "critical"
  title: string
  detail: string
  created_at: string
  read: boolean
}

export const getRestaurants = async (): Promise<{ restaurants: OperatedRestaurant[]; total: number }> => {
  const res = await API.get("/ops/restaurants")
  return res.data
}

export const getOperatedAlerts = async (): Promise<{ alerts: OperatedAlert[] }> => {
  const res = await API.get("/ops/alerts", { params: { limit: 50 } })
  return res.data
}
