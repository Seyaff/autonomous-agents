"use client"

import * as React from "react"
import { useRouter } from "next/navigation"

import {
  Dialog,
  DialogContent,
} from "@/components/ui/dialog"
import { Progress } from "@/components/ui/progress"
import { useAuth } from "@/components/providers/auth-provider"
import { useSetupState } from "@/hooks/setup/use-setup-state"
import { NUMBERED_STEPS, stepNumber, type SetupRoute } from "@/lib/setup"

const WIDTH: Record<SetupRoute, string> = {
  welcome: "sm:max-w-lg",
  restaurant: "sm:max-w-lg",
  menu: "sm:max-w-lg",
  hours: "sm:max-w-xl",
  agent: "sm:max-w-xl",
  test: "sm:max-w-3xl",
  whatsapp: "sm:max-w-lg",
  done: "sm:max-w-lg",
}

/** The persistent setup dialog. It lives in setup/layout.tsx, so it stays
 * mounted while the URL changes between steps. Only the content inside swaps.
 *
 * Until setup is finished there's no close button, and outside clicks and
 * Escape are ignored. Browser back and typed URLs are handled by the auth gate. */
export function SetupDialog({ step, children }: { step: SetupRoute; children: React.ReactNode }) {
  const router = useRouter()
  const { activeTenantId } = useAuth()
  const setup = useSetupState({ enabled: !!activeTenantId })

  const dismissible =
    setup.isComplete &&
    (step === "menu" || step === "whatsapp") &&
    setup.skippedSteps.includes(step)

  const number = stepNumber(step)

  return (
    <Dialog
      open
      disablePointerDismissal={!dismissible}
      onOpenChange={(open) => {
        if (!open && dismissible) router.push("/dashboard")
      }}
    >
      <DialogContent
        showCloseButton={dismissible}
        overlayClassName="bg-black/40 backdrop-blur-sm"
        className={WIDTH[step]}
      >
        {number !== null && (
          <div className="space-y-2">
            <div className="flex items-center justify-between font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
              <span>Step {number} of {NUMBERED_STEPS}</span>
            </div>
            <Progress value={(number / NUMBERED_STEPS) * 100} />
          </div>
        )}
        <div key={step} className="motion-safe:animate-in motion-safe:fade-in-0 motion-safe:zoom-in-95 grid gap-4">
          {children}
        </div>
      </DialogContent>
    </Dialog>
  )
}
