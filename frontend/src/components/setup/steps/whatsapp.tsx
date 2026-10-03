"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { useQueryClient } from "@tanstack/react-query"
import { CheckCircle2Icon } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { DialogDescription, DialogFooter, DialogTitle } from "@/components/ui/dialog"
import { MetaEmbeddedSignup } from "@/components/MetaEmbeddedSignup"
import { useAuth } from "@/components/providers/auth-provider"
import { useSetupState, SETUP_QUERY_KEY } from "@/hooks/setup/use-setup-state"
import { useSetupStep } from "@/hooks/setup/use-setup-step"
import { StepError } from "@/components/setup/steps/common"

export function WhatsAppStep() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const { activeTenantId } = useAuth()
  const setup = useSetupState({ enabled: !!activeTenantId })
  const { complete } = useSetupStep()

  const [justConnected, setJustConnected] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const connected = justConnected || !!setup.tenant?.whatsapp_connected
  const number = setup.tenant?.display_phone_number

  async function markConnected() {
    setJustConnected(true)
    setError(null)
    // The server saved the connection. Reload the tenant so the number shows.
    await queryClient.invalidateQueries({ queryKey: SETUP_QUERY_KEY })
    complete.mutate({ step: "whatsapp", action: "complete" })
  }

  return (
    <>
      <div className="space-y-1.5">
        <DialogTitle className="font-heading text-lg">Connect WhatsApp</DialogTitle>
        <DialogDescription>
          Customers message this number. Your agent answers from it.
        </DialogDescription>
      </div>

      {connected ? (
        <Alert>
          <CheckCircle2Icon className="size-4 text-ok" />
          <AlertTitle>Connected{number ? ` to ${number}` : ""}</AlertTitle>
          <AlertDescription>Your agent can now answer customers on WhatsApp.</AlertDescription>
        </Alert>
      ) : (
        <>
          <Alert>
            <AlertTitle>Use a number that isn&apos;t in WhatsApp already</AlertTitle>
            <AlertDescription>
              The phone number must not be active in the WhatsApp or WhatsApp Business app. You can move an
              existing number, but its chat history won&apos;t come along.
            </AlertDescription>
          </Alert>
          <ul className="list-disc space-y-1 pl-4 text-sm text-muted-foreground">
            <li>A Facebook account that manages your business</li>
            <li>A phone number that can receive an SMS or a call</li>
            <li>Your business name, and a website or Facebook page</li>
          </ul>
          <MetaEmbeddedSignup
            next="/setup/whatsapp"
            onSuccess={markConnected}
            onError={(message) => setError(message)}
          />
        </>
      )}

      <StepError message={error ?? (complete.isError ? "Could not save this step. Try again." : null)} />

      <DialogFooter>
        <Button variant="outline" onClick={() => router.push("/setup/test")}>
          Back
        </Button>
        {!connected && (
          <Button
            variant="ghost"
            disabled={complete.isPending}
            onClick={() =>
              complete.mutate({ step: "whatsapp", action: "skip" }, { onSuccess: () => router.push("/setup/done") })
            }
          >
            Do this later
          </Button>
        )}
        {connected && (
          <Button
            disabled={complete.isPending}
            onClick={() =>
              complete.mutate({ step: "whatsapp", action: "complete" }, { onSuccess: () => router.push("/setup/done") })
            }
          >
            Continue
          </Button>
        )}
      </DialogFooter>
    </>
  )
}
