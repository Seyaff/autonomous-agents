import API from "@/lib/axios-client"

export type TemplateStatus = "APPROVED" | "PENDING" | "REJECTED" | "PAUSED" | "DISABLED" | "IN_APPEAL" | string
export type TemplateCategory = "MARKETING" | "UTILITY"

export interface TemplateButtonPayload {
  type: "QUICK_REPLY" | "URL" | "PHONE_NUMBER"
  text: string
  url?: string
  phone_number?: string
}

/** A template as last synced from Meta. */
export interface WaTemplate {
  meta_id: string | null
  name: string
  language: string
  status: TemplateStatus
  category: string
  rejected_reason: string | null
  header_text: string | null
  header_format: string | null
  body_text: string
  footer_text: string | null
  buttons: { type: string; text: string; url?: string; phone_number?: string }[]
  body_variables: number
  header_variables: number
  synced_at: string
}

export interface TemplateList {
  templates: WaTemplate[]
  synced_at: string | null
  languages: Record<string, string>
  whatsapp_connected: boolean
}

export interface TemplateDraftPayload {
  name: string
  category: TemplateCategory
  language: string
  header_text?: string | null
  header_example?: string | null
  body: string
  body_examples: string[]
  footer?: string | null
  buttons: TemplateButtonPayload[]
}

export const listTemplates = async (status?: string): Promise<TemplateList> => {
  const res = await API.get("/templates", { params: status ? { status } : undefined })
  return res.data
}

export const syncTemplates = async () => {
  const res = await API.post("/templates/sync")
  return res.data as { templates: WaTemplate[] }
}

export const createTemplate = async (payload: TemplateDraftPayload) => {
  const res = await API.post("/templates", payload)
  return res.data.template as WaTemplate
}

export const deleteTemplate = async (name: string, language: string) => {
  const res = await API.delete(`/templates/${encodeURIComponent(name)}`, { params: { language } })
  return res.data
}

export interface OrderUpdatesState {
  configured: boolean
  template: WaTemplate | null
}

export const getOrderUpdates = async (): Promise<OrderUpdatesState> => {
  const res = await API.get("/templates/order-updates")
  return res.data
}

export const setUpOrderUpdates = async (language = "en"): Promise<OrderUpdatesState> => {
  const res = await API.post("/templates/order-updates", null, { params: { language } })
  return res.data
}

/** Variables in a template's text: {{1}}, {{2}} ... in order of first use. */
export function variablesIn(text: string): number[] {
  const found = [...text.matchAll(/\{\{\s*(\d+)\s*\}\}/g)].map((m) => Number(m[1]))
  return [...new Set(found)]
}

/** The template filled with values, as the customer would read it. */
export function fillTemplate(text: string, values: string[]): string {
  return text.replace(/\{\{\s*(\d+)\s*\}\}/g, (whole, n) => values[Number(n) - 1]?.trim() || whole)
}
