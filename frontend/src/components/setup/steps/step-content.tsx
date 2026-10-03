"use client"

import * as React from "react"
import { useRouter } from "next/navigation"

import { useAuth } from "@/components/providers/auth-provider"
import { useSetupState } from "@/hooks/setup/use-setup-state"
import { useSetupStep } from "@/hooks/setup/use-setup-step"
import { StepError } from "@/components/setup/steps/common"
import { WelcomeStep } from "@/components/setup/steps/welcome"
import { DoneStep } from "@/components/setup/steps/done"
import { RestaurantStep } from "@/components/setup/steps/restaurant"
import { MenuStep } from "@/components/setup/steps/menu"
import { HoursStep } from "@/components/setup/steps/hours"
import { AgentStep } from "@/components/setup/steps/agent"
import { TestStep } from "@/components/setup/steps/test"
import { WhatsAppStep } from "@/components/setup/steps/whatsapp"
import type { SetupRoute } from "@/lib/setup"

/** The body and footer for one setup step. Each step saves through the server
 * before it moves on, so the gate and the progress stay in step with the screen. */
export function SetupStepContent({ step }: { step: SetupRoute }) {
  const router = useRouter()
  const { activeTenantId } = useAuth()
  const setup = useSetupState({ enabled: !!activeTenantId })
  const { finish } = useSetupStep()
  const [error, setError] = React.useState<string | null>(null)

  switch (step) {
    case "welcome":
      return <WelcomeStep />
    case "restaurant":
      return <RestaurantStep />
    case "menu":
      return <MenuStep />
    case "hours":
      return <HoursStep />
    case "agent":
      return <AgentStep />
    case "test":
      return <TestStep />
    case "whatsapp":
      return <WhatsAppStep />
    case "done":
      return (
        <DoneStep
          whatsappConnected={!!setup.tenant?.whatsapp_connected}
          skipped={setup.skippedSteps}
          saving={finish.isPending}
          error={error}
          onFinish={() => {
            setError(null)
            finish.mutate(undefined, {
              onSuccess: () => router.replace("/dashboard"),
              onError: () => setError("Could not finish setup. Try again."),
            })
          }}
        />
      )
    default:
      return <StepError message="Unknown setup step." />
  }
}
