"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  getTenantSettings,
  setAgentEnabled,
  updateTenantSettings,
  type TenantSettingsUpdate,
} from "@/services/tenant/tenant.service"
import { USE_MOCKS } from "@/lib/mocks"

const KEY = ["tenant", "settings"] as const

export function useTenantSettings() {
  const queryClient = useQueryClient()
  const tenant = useQuery({
    queryKey: KEY,
    queryFn: getTenantSettings,
    enabled: !USE_MOCKS,
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: KEY })
    queryClient.invalidateQueries({ queryKey: ["tenant", "current"] })
  }

  const update = useMutation({
    mutationFn: (payload: TenantSettingsUpdate) => updateTenantSettings(payload),
    onSuccess: refresh,
  })

  const toggleAgent = useMutation({
    mutationFn: (enabled: boolean) => setAgentEnabled(enabled),
    onSuccess: refresh,
  })

  return { tenant, update, toggleAgent }
}
