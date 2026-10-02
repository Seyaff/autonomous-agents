"use client"

import { useQuery } from "@tanstack/react-query"
import {
  getCurrentTenant,
  toTenantSummary,
  type TenantSummary,
} from "@/services/tenant/tenant.service"
import { MOCK_ACTIVE_TENANT_ID, MOCK_TENANTS } from "@/lib/mock/tenant"
import { USE_MOCKS } from "@/lib/mocks"

export const useCurrentTenant = () => {
  return useQuery<TenantSummary>({
    queryKey: ["tenant", "current", USE_MOCKS],
    queryFn: async () => {
      if (USE_MOCKS) {
        const tenant = MOCK_TENANTS.find((t) => t.tenant_id === MOCK_ACTIVE_TENANT_ID)
        if (!tenant) throw new Error("Mock active tenant not found")
        return tenant
      }
      return toTenantSummary(await getCurrentTenant())
    },
    staleTime: 5 * 60 * 1000,
  })
}
