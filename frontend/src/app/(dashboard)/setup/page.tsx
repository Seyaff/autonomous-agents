"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { useAuth } from "@/components/providers/auth-provider"
import { useSetupState } from "@/hooks/setup/use-setup-state"

/** /setup has no step of its own. It sends the owner to where they left off. */
export default function SetupIndexPage() {
  const router = useRouter()
  const { activeTenantId } = useAuth()
  const setup = useSetupState({ enabled: !!activeTenantId })

  React.useEffect(() => {
    if (!activeTenantId) {
      router.replace("/setup/welcome")
    } else if (setup.tenant) {
      router.replace(setup.isComplete ? "/dashboard" : `/setup/${setup.currentStep}`)
    }
  }, [activeTenantId, setup.tenant, setup.isComplete, setup.currentStep, router])

  return null
}
