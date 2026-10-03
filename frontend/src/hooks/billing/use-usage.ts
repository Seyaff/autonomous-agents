"use client"

import { useQuery } from "@tanstack/react-query"
import { getUsage } from "@/services/billing/billing.service"
import { USE_MOCKS } from "@/lib/mocks"
import { useAuth } from "@/components/providers/auth-provider"

export function useUsage() {
  // Usage belongs to a restaurant. Before setup creates one there's nothing to ask for.
  const { activeTenantId } = useAuth()
  return useQuery({
    queryKey: ["billing", "usage"],
    queryFn: getUsage,
    enabled: !USE_MOCKS && !!activeTenantId,
    staleTime: 60 * 1000,
  })
}
