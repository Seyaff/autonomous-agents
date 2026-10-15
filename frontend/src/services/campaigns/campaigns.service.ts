import API from "@/lib/axios-client"

export interface ParamSource {
  kind: "text" | "customer_name"
  value: string
}

export interface Audience {
  kind: "all" | "ordered_within_days" | "phones"
  days?: number | null
  phones?: string[]
}

export interface CampaignCounts {
  total: number
  sent: number
  delivered: number
  read: number
  failed: number
  skipped_opted_out: number
}

export interface Campaign {
  campaign_id: string
  name: string
  template_name: string
  language: string
  category: string | null
  audience: Audience
  status: "sending" | "done" | "failed" | "paused"
  counts: CampaignCounts
  created_at: string
  finished_at: string | null
  error: string | null
  stalled: boolean
}

export interface CampaignCreatePayload {
  name: string
  template_name: string
  language: string
  body_params: ParamSource[]
  header_params: ParamSource[]
  audience: Audience
}

export const listCampaigns = async (): Promise<{ campaigns: Campaign[] }> => {
  const res = await API.get("/campaigns")
  return res.data
}

export const previewAudience = async (audience: Audience) => {
  const res = await API.post("/campaigns/audience", audience)
  return res.data as { count: number; skipped_opted_out: number; sample: string[] }
}

export const sendCampaign = async (payload: CampaignCreatePayload) => {
  const res = await API.post("/campaigns", payload)
  return res.data.campaign as Campaign
}

export const getCampaign = async (campaignId: string) => {
  const res = await API.get(`/campaigns/${campaignId}`)
  return res.data as { campaign: Campaign; failed: { phone: string; name: string; error: string | null }[] }
}

export const resumeCampaign = async (campaignId: string) => {
  const res = await API.post(`/campaigns/${campaignId}/resume`)
  return res.data
}
