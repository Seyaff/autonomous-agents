"use client"

import { useQuery } from "@tanstack/react-query"
import { getOrderStatsSummary } from "@/services/orders/orders.service"

export const useOrderStats = () => {
  return useQuery({
    queryKey: ["orders", "stats"],
    queryFn: getOrderStatsSummary,
    staleTime: 30 * 1000,
  })
}
