"use client"

import { useQuery } from "@tanstack/react-query"
import { getUsage } from "@/services/billing/billing.service"
import { USE_MOCKS } from "@/lib/mocks"

export function useUsage() {
  return useQuery({
    queryKey: ["billing", "usage"],
    queryFn: getUsage,
    enabled: !USE_MOCKS,
    staleTime: 60 * 1000,
  })
}
