"use client"

import { useQuery } from "@tanstack/react-query"
import { getSetupTenant } from "@/services/setup/setup.service"

export const SETUP_QUERY_KEY = ["setup", "state"] as const

/** Where the owner is in setup, read from the server. The auth gate, the step
 * pages and the dashboard card all use this one query. */
export function useSetupState({ enabled }: { enabled: boolean }) {
  const query = useQuery({
    queryKey: SETUP_QUERY_KEY,
    queryFn: getSetupTenant,
    enabled,
    retry: false,
    staleTime: 30 * 1000,
  })

  const setup = query.data?.setup
  return {
    tenant: query.data,
    isLoading: enabled && query.isLoading,
    isError: query.isError,
    currentStep: query.data?.setup_current_step ?? "restaurant",
    completedSteps: setup?.completed_steps ?? [],
    skippedSteps: setup?.skipped_steps ?? [],
    isComplete: Boolean(setup?.completed_at),
  }
}
