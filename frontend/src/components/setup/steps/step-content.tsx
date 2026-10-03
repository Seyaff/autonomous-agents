"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from "@/components/ui/dialog"
import { useSetupStep } from "@/hooks/setup/use-setup-step"
import { useSetupState } from "@/hooks/setup/use-setup-state"
import { useAuth } from "@/components/providers/auth-provider"
import { nextRoute, type SetupRoute } from "@/lib/setup"
import { WelcomeStep } from "@/components/setup/steps/welcome"
import { DoneStep } from "@/components/setup/steps/done"

// Previous step for Back. Welcome and restaurant have none.
const PREVIOUS: Partial<Record<SetupRoute, SetupRoute>> = {
  menu: "restaurant",
  hours: "menu",
  agent: "hours",
  test: "agent",
  whatsapp: "test",
}

const TITLES: Record<SetupRoute, { title: string; description: string }> = {
  welcome: { title: "Welcome to Siyaf", description: "" },
  restaurant: { title: "Restaurant details", description: "" },
  menu: { title: "Upload your menu", description: "" },
  hours: { title: "Hours and delivery", description: "" },
  agent: { title: "Set up your agent", description: "" },
  test: { title: "Test your agent", description: "" },
  whatsapp: { title: "Connect WhatsApp", description: "" },
  done: { title: "You're almost set", description: "" },
}

/** The body and footer for one setup step. Welcome and done are complete.
 * The others are placeholders until their forms are built, but they still
 * call the real setup endpoints, so the gate and the progress can be tested. */
export function SetupStepContent({ step }: { step: SetupRoute }) {
  const router = useRouter()
  const { activeTenantId } = useAuth()
  const setup = useSetupState({ enabled: !!activeTenantId })
  const { complete, finish } = useSetupStep()
  const [error, setError] = React.useState<string | null>(null)

  if (step === "welcome") return <WelcomeStep />
  if (step === "done") {
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
  }

  const { title } = TITLES[step]
  const back = PREVIOUS[step]
  const optional = step === "menu" || step === "whatsapp"
  const saving = complete.isPending

  function advance(action: "complete" | "skip") {
    setError(null)
    complete.mutate(
      { step, action },
      {
        onSuccess: () => router.push(`/setup/${nextRoute(step)}`),
        onError: (err: unknown) => {
          const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
          setError(detail ?? "Could not save this step. Try again.")
          toast.error("Could not save this step.")
        },
      }
    )
  }

  return (
    <>
      <div className="space-y-1.5">
        <DialogTitle className="font-heading text-lg">{title}</DialogTitle>
        <DialogDescription>
          Built in the next part of the setup work. Continue saves this step so the rest of the flow can be tested.
        </DialogDescription>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <DialogFooter>
        {back && (
          <Button variant="outline" onClick={() => router.push(`/setup/${back}`)} disabled={saving}>
            Back
          </Button>
        )}
        {optional && (
          <Button variant="ghost" onClick={() => advance("skip")} disabled={saving}>
            {step === "menu" ? "Skip for now" : "Do this later"}
          </Button>
        )}
        <Button onClick={() => advance("complete")} disabled={saving}>
          {saving ? "Saving..." : "Continue"}
        </Button>
      </DialogFooter>
    </>
  )
}
