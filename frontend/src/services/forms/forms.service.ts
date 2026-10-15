import API from "@/lib/axios-client"

export type FieldKind =
  | "short_text"
  | "long_text"
  | "email"
  | "phone"
  | "number"
  | "date"
  | "dropdown"
  | "choice"
  | "checkboxes"
  | "opt_in"

export const FIELD_KINDS: { value: FieldKind; label: string; limit: number; options?: boolean }[] = [
  { value: "short_text", label: "Short text", limit: 20 },
  { value: "long_text", label: "Long text", limit: 20 },
  { value: "phone", label: "Phone number", limit: 20 },
  { value: "email", label: "Email", limit: 20 },
  { value: "number", label: "Number", limit: 20 },
  { value: "date", label: "Date", limit: 40 },
  { value: "dropdown", label: "Dropdown", limit: 20, options: true },
  { value: "choice", label: "Pick one", limit: 30, options: true },
  { value: "checkboxes", label: "Pick several", limit: 30, options: true },
  { value: "opt_in", label: "Checkbox to agree", limit: 120 },
]

export const FORM_CATEGORIES: { value: string; label: string }[] = [
  { value: "APPOINTMENT_BOOKING", label: "Booking" },
  { value: "LEAD_GENERATION", label: "Enquiry or lead" },
  { value: "CONTACT_US", label: "Contact us" },
  { value: "CUSTOMER_SUPPORT", label: "Support" },
  { value: "SURVEY", label: "Survey or feedback" },
  { value: "SIGN_UP", label: "Sign up" },
  { value: "OTHER", label: "Other" },
]

export interface FormField {
  label: string
  kind: FieldKind
  required: boolean
  options: string[]
  helper?: string | null
  name?: string | null
}

export interface FormScreen {
  title: string
  intro?: string | null
  fields: FormField[]
}

export interface FormDraftPayload {
  name: string
  purpose: string
  body: string
  cta: string
  submit_label: string
  category: string
  screens: FormScreen[]
}

export interface WaForm extends FormDraftPayload {
  form_id: string
  status: "draft" | "published" | "error"
  meta_status: "DRAFT" | "PUBLISHED" | null
  meta_flow_id: string | null
  version: number
  validation_errors: string[]
  has_unpublished_changes: boolean
  responses: number
  published_at: string | null
  updated_at: string
}

export interface FormResponse {
  response_id: string
  form_id: string
  form_name: string
  customer_phone: string
  answers: { label: string; value: string }[]
  received_at: string
}

export const listForms = async (): Promise<{ forms: WaForm[]; whatsapp_connected: boolean }> => {
  const res = await API.get("/forms")
  return res.data
}

export const createForm = async (payload: FormDraftPayload) => {
  const res = await API.post("/forms", payload)
  return res.data.form as WaForm
}

export const updateForm = async (formId: string, payload: FormDraftPayload) => {
  const res = await API.put(`/forms/${formId}`, payload)
  return res.data.form as WaForm
}

export const publishForm = async (formId: string) => {
  const res = await API.post(`/forms/${formId}/publish`, null, { timeout: 60_000 })
  return res.data.form as WaForm
}

export const deleteForm = async (formId: string) => {
  const res = await API.delete(`/forms/${formId}`)
  return res.data
}

export const getFormPreview = async (formId: string) => {
  const res = await API.get(`/forms/${formId}/preview`)
  return res.data as { preview_url: string | null }
}

export const listFormResponses = async (formId: string) => {
  const res = await API.get(`/forms/${formId}/responses`)
  return res.data as { responses: FormResponse[] }
}
