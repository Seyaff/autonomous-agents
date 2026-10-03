import API from "@/lib/axios-client"

export interface SetupProgress {
  completed_steps: string[]
  skipped_steps: string[]
  completed_at: string | null
}

/** The fields the setup flow needs from GET /tenant/current. */
export interface SetupTenant {
  tenant_id: string
  business_name: string
  currency: string
  timezone: string
  setup: SetupProgress
  setup_current_step: string
  whatsapp_connected?: boolean
  display_phone_number?: string | null
  order_types?: string[]
  operating_hours?: Array<Record<string, unknown>>
  delivery_areas?: string[]
  payment_methods?: string[]
  min_order_amount?: number
  delivery_settings?: { flat_delivery_fee?: number; avg_prep_time_minutes?: number }
  agent_settings?: Partial<AgentSettingsPayload>
  country?: string | null
  city?: string | null
}

export const getSetupTenant = async (): Promise<SetupTenant> => {
  const res = await API.get("/tenant/current")
  return res.data
}

export type SetupAction = "complete" | "skip"

export const postSetupStep = async (step: string, action: SetupAction): Promise<SetupProgress> => {
  const res = await API.post(`/tenant/current/setup/${step}`, { action })
  return res.data
}

export const finishSetup = async (): Promise<SetupProgress> => {
  const res = await API.post("/tenant/current/setup/finish")
  return res.data
}

export interface TestChatReply {
  reply: string
  trace: { tool: string; args: Record<string, unknown>; result_summary: string }[]
  escalated: boolean
}

export interface TestChatMessage {
  role: "customer" | "agent"
  content: string
  trace?: TestChatReply["trace"]
  escalated?: boolean
  at: string
}

export const sendTestMessage = async (message: string): Promise<TestChatReply> => {
  const res = await API.post("/agent/test", { message })
  return res.data
}

export const getTestTranscript = async (): Promise<TestChatMessage[]> => {
  const res = await API.get("/agent/test")
  return res.data.messages
}

export const resetTestChat = async () => {
  await API.delete("/agent/test")
}

export interface MenuItem {
  name: string
  category: string
  price: number | null
  description: string
}

export const getMenuItems = async (): Promise<{ items: MenuItem[]; source_filename: string | null }> => {
  const res = await API.get("/tenant/current/menu-items")
  return res.data
}

export type CountryCode = "PK" | "AE" | "SA" | "GB" | "US"
export type OrderType = "delivery" | "takeaway" | "dine_in"
export type PaymentMethod = "cash_on_delivery" | "card_on_delivery" | "bank_transfer"

export interface CreateRestaurantPayload {
  business_name: string
  country: CountryCode
  city?: string
  order_types: OrderType[]
}

export const createRestaurant = async (payload: CreateRestaurantPayload) => {
  const res = await API.post("/tenant/create", payload)
  return res.data as { tenant_id: string }
}

export interface DayHoursPayload {
  day: string
  open: string
  close: string
  closed: boolean
}

export interface RestaurantUpdatePayload {
  business_name?: string
  order_types?: OrderType[]
  operating_hours?: DayHoursPayload[]
  flat_delivery_fee?: number
  min_order_amount?: number
  avg_prep_time_minutes?: number
  delivery_areas?: string[]
  payment_methods?: PaymentMethod[]
}

export const updateRestaurant = async (payload: RestaurantUpdatePayload) => {
  const res = await API.patch("/tenant/current", payload)
  return res.data
}

export interface AgentSettingsPayload {
  language: "match" | "en" | "roman_urdu"
  tone: "warm" | "professional" | "short"
  greeting: string | null
  escalate_on: {
    refund: boolean
    complaint: boolean
    human_requested: boolean
    large_order_over: number | null
  }
}

export const saveAgentSettings = async (payload: AgentSettingsPayload) => {
  const res = await API.patch("/tenant/current/agent-settings", payload)
  return res.data
}

export type MenuJobStatus = "queued" | "running" | "done" | "failed"
export type MenuJobStage = "received" | "indexing" | "reading" | "saving" | "done" | "failed"

export interface MenuJob {
  id: string
  job_id: string
  filename: string
  status: MenuJobStatus
  stage: MenuJobStage
  label: string
  chunks_done: number
  chunks_total: number
  items_found: number
  error: string | null
  created_at: string
  updated_at: string
}

/** Starts reading a menu in the background. Returns at once with a job to poll. */
export const uploadMenuPdf = async (file: File): Promise<{ job_id: string }> => {
  const form = new FormData()
  form.append("file", file)
  // Only the upload itself is sent now. Reading happens on the server, so the
  // request returns in well under a second.
  const res = await API.post("/tenant/upload-menu-pdf", form, { timeout: 60_000 })
  return res.data
}

export const getMenuUpload = async (jobId: string): Promise<MenuJob> => {
  const res = await API.get(`/tenant/menu-uploads/${jobId}`)
  return res.data.job
}

export const getLatestMenuUpload = async (): Promise<MenuJob | null> => {
  const res = await API.get("/tenant/menu-uploads/latest")
  return res.data.job
}
