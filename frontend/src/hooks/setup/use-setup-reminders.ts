"use client"

import { useAuth } from "@/components/providers/auth-provider"
import { useSetupState } from "@/hooks/setup/use-setup-state"

/** Optional steps the owner skipped, still to finish after setup. Empty until setup is complete. */
export function useSetupReminders() {
  const { activeTenantId } = useAuth()
  const setup = useSetupState({ enabled: !!activeTenantId })
  const remaining = setup.isComplete
    ? setup.skippedSteps.filter((s) => s === "menu" || s === "whatsapp")
    : []
  return { remaining }
}
