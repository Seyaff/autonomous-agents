"use client"

import { useQuery } from "@tanstack/react-query"
import { getCurrentTenant } from "@/services/tenant/tenant.service"

export const useCurrentTenant = () => {
  return useQuery({
    queryKey: ["tenant", "current"],
    queryFn: getCurrentTenant,
    staleTime: 5 * 60 * 1000,
  })
}
