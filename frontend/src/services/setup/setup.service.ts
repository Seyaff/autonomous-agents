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
