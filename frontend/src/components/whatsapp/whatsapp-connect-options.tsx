"use client"

import * as React from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { MetaEmbeddedSignup } from "@/components/MetaEmbeddedSignup"
import API from "@/lib/axios-client"

type Mode = "meta" | "manual"

function errorText(err: unknown) {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Could not connect WhatsApp."
}

/**
 * Two ways to connect a restaurant's number: the Meta popup, or the details copied in by hand.
 * Both run the same checks on the server and store the token encrypted.
 */
export function WhatsAppConnectOptions({
  next = "/setup",
  onSuccess,
  onError,
}: {
  next?: string
  onSuccess: () => void
  onError: (message: string) => void
}) {
  const [mode, setMode] = React.useState<Mode>("meta")

  return (
    <div className="space-y-4">
      <div role="tablist" className="inline-flex rounded-md border p-0.5 text-sm">
        {([
          ["meta", "Connect with Meta"],
          ["manual", "Enter details by hand"],
        ] as [Mode, string][]).map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={mode === value}
            onClick={() => setMode(value)}
            className={`rounded px-3 py-1 ${mode === value ? "bg-foreground text-background" : "text-muted-foreground"}`}
          >
            {label}
          </button>
        ))}
      </div>

      {mode === "meta" ? (
        <MetaEmbeddedSignup next={next} onSuccess={onSuccess} onError={onError} />
      ) : (
        <ManualForm onSuccess={onSuccess} onError={onError} />
      )}
    </div>
  )
}

function ManualForm({ onSuccess, onError }: { onSuccess: () => void; onError: (message: string) => void }) {
  const [phoneNumberId, setPhoneNumberId] = React.useState("")
  const [wabaId, setWabaId] = React.useState("")
  const [token, setToken] = React.useState("")
  const [saving, setSaving] = React.useState(false)

  const ready = phoneNumberId.trim() && wabaId.trim() && token.trim().length >= 20

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    try {
      await API.post("/tenant/whatsapp/manual", {
        phone_number_id: phoneNumberId.trim(),
        waba_id: wabaId.trim(),
        access_token: token.trim(),
      })
      onSuccess()
    } catch (err) {
      onError(errorText(err))
    } finally {
      // Never keep the token in the page once it's been sent.
      setToken("")
      setSaving(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="wa-phone-id">Phone number ID</Label>
        <Input id="wa-phone-id" inputMode="numeric" value={phoneNumberId} onChange={(e) => setPhoneNumberId(e.target.value)} placeholder="e.g. 123456789012345" autoComplete="off" />
        <p className="text-xs text-muted-foreground">
          In Meta Business Manager, open WhatsApp → API Setup. Pick the number, and copy its Phone number ID.
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="wa-waba-id">WhatsApp Business Account ID</Label>
        <Input id="wa-waba-id" inputMode="numeric" value={wabaId} onChange={(e) => setWabaId(e.target.value)} placeholder="e.g. 987654321098765" autoComplete="off" />
        <p className="text-xs text-muted-foreground">Shown on the same API Setup page, above the phone number.</p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="wa-token">Access token</Label>
        <Input id="wa-token" type="password" value={token} onChange={(e) => setToken(e.target.value)} placeholder="Paste the permanent token" autoComplete="off" />
        <p className="text-xs text-muted-foreground">
          Use a permanent token from a System User that can manage WhatsApp, with this app assigned to it. It's
          stored encrypted and never shown again.
        </p>
      </div>

      <div className="flex justify-end">
        <Button type="submit" disabled={!ready || saving}>
          {saving ? "Checking with Meta…" : "Connect number"}
        </Button>
      </div>
    </form>
  )
}
