import API from "@/lib/axios-client"

export type AlertSeverity = "info" | "warning" | "critical"

export interface OwnerAlert {
  id: string
  kind: string
  severity: AlertSeverity
  title: string
  detail: string
  created_at: string
  read_at: string | null
  owner_notified_whatsapp: boolean
}

export interface AlertsResponse {
  alerts: OwnerAlert[]
  unread_count: number
}

export const listAlerts = async (): Promise<AlertsResponse> => {
  const res = await API.get("/alerts", { params: { limit: 30 } })
  return res.data
}

export const markAlertRead = async (id: string) => {
  await API.post(`/alerts/${id}/read`)
}

export const markAllAlertsRead = async () => {
  await API.post("/alerts/read-all")
}
