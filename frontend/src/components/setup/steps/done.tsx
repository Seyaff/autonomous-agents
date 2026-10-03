"use client"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { DialogDescription, DialogFooter, DialogTitle } from "@/components/ui/dialog"

const LABELS: Record<string, string> = {
  menu: "Upload your menu",
  whatsapp: "Connect WhatsApp",
}

export function DoneStep({
  whatsappConnected,
  skipped,
  saving,
  error,
  onFinish,
}: {
  whatsappConnected: boolean
  skipped: string[]
  saving: boolean
  error: string | null
  onFinish: () => void
}) {
  const live = whatsappConnected
  return (
    <>
      <div className="space-y-2">
        <DialogTitle className="font-heading text-lg">
          {live ? "You're live" : "You're almost set"}
        </DialogTitle>
        <DialogDescription>
          {live
            ? "Your agent now answers customers on WhatsApp. Conversations and orders appear in your dashboard."
            : "Your agent is in test mode until WhatsApp is connected. Anything you skipped stays on your dashboard checklist."}
        </DialogDescription>
      </div>

      {skipped.length > 0 && (
        <ul className="list-disc space-y-1 pl-4 text-sm">
          {skipped.map((s) => (
            <li key={s}>{LABELS[s] ?? s}</li>
          ))}
        </ul>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <DialogFooter>
        <Button onClick={onFinish} disabled={saving}>
          {saving ? "Finishing..." : "Go to dashboard"}
        </Button>
      </DialogFooter>
    </>
  )
}
