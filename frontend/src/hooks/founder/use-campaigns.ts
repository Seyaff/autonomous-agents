"use client"

import { useQuery } from "@tanstack/react-query"
import { listCampaigns } from "@/services/founder/founder.service"

export const useCampaigns = () => {
  return useQuery({
    queryKey: ["founder", "campaigns"],
    queryFn: listCampaigns,
  })
}
