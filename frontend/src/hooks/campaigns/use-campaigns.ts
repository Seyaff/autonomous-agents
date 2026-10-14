"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  getCampaign,
  listCampaigns,
  resumeCampaign,
  sendCampaign,
  type CampaignCreatePayload,
} from "@/services/campaigns/campaigns.service"
import { USE_MOCKS } from "@/lib/mocks"

const KEY = ["campaigns"] as const

/** Campaigns refresh every few seconds while one is sending, so the totals move. */
export function useCampaigns() {
  return useQuery({
    queryKey: KEY,
    queryFn: listCampaigns,
    enabled: !USE_MOCKS,
    refetchInterval: (query) =>
      query.state.data?.campaigns.some((c) => c.status === "sending") ? 3000 : 30000,
  })
}

export function useCampaign(campaignId: string | null) {
  return useQuery({
    queryKey: [...KEY, campaignId],
    queryFn: () => getCampaign(campaignId as string),
    enabled: !!campaignId && !USE_MOCKS,
    refetchInterval: (query) => (query.state.data?.campaign.status === "sending" ? 3000 : false),
  })
}

export function useCampaignActions() {
  const queryClient = useQueryClient()
  const refresh = () => queryClient.invalidateQueries({ queryKey: KEY })
  return {
    send: useMutation({ mutationFn: (payload: CampaignCreatePayload) => sendCampaign(payload), onSuccess: refresh }),
    resume: useMutation({ mutationFn: (campaignId: string) => resumeCampaign(campaignId), onSuccess: refresh }),
  }
}
