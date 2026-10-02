"use client"

import { useQuery } from "@tanstack/react-query"
import { get7DaySummary } from "@/services/analytics/analytics.service"

export const use7DaySummary = (options?: { enabled?: boolean }) => {
  return useQuery({
    queryKey: ["analytics", "7day-summary"],
    queryFn: get7DaySummary,
    staleTime: 60 * 1000,
    enabled: options?.enabled ?? true,
  })
}
