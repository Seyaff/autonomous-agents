import API from "@/lib/axios-client"

export interface LeadHuntResult {
  status: string
  campaign_id: string
  query: string
  total_leads: number
  breakdown: { hot: number; warm: number; premium: number }
  export_file: string
  leads: Array<Record<string, unknown>>
}

export interface Campaign {
  campaign_id: string
  founder_id: string
  query: string
  total_leads: number
  hot_count: number
  warm_count: number
  premium_count: number
  filename: string
  created_at: string
}

export const huntLeads = async (
  query: string,
  maxLeads: number
): Promise<LeadHuntResult> => {
  const res = await API.post("/founder/lead-hunt", { query, max_leads: maxLeads })
  return res.data
}

export const listCampaigns = async (): Promise<Campaign[]> => {
  const res = await API.get("/founder/campaigns")
  return res.data
}

/** Relative path through the /api rewrite — a normal navigation/download
 * click carries the auth cookie, no fetch needed. */
export const getCampaignExportPath = (campaignId: string) =>
  `/api/founder/campaigns/${campaignId}/export`
