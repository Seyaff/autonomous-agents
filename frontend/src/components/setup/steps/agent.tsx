"use client"

import * as React from "react"
import { useRouter } from "next/navigation"

import { Button } from "@/components/ui/button"
import { DialogDescription, DialogFooter, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { useAuth } from "@/components/providers/auth-provider"
import { useSetupState } from "@/hooks/setup/use-setup-state"
import { useSetupStep } from "@/hooks/setup/use-setup-step"
import { saveAgentSettings, type AgentSettingsPayload } from "@/services/setup/setup.service"
import { StepError, errorDetail } from "@/components/setup/steps/common"

type Language = AgentSettingsPayload["language"]
type Tone = AgentSettingsPayload["tone"]

const LANGUAGES: { value: Language; label: string }[] = [
  { value: "match", label: "Match the customer" },
  { value: "en", label: "English" },
  { value: "roman_urdu", label: "Roman Urdu" },
]

const TONES: { value: Tone; label: string }[] = [
  { value: "warm", label: "Warm" },
  { value: "professional", label: "Professional" },
  { value: "short", label: "Short and quick" },
]

function suggestedGreeting(name: string, language: Language) {
  const shop = name.trim() || "our restaurant"
  if (language === "en") return `Hi, welcome to ${shop}! How can I help?`
  return `Salam! ${shop} mein khush amdeed. Kya order krna hai?`
}

export function AgentStep() {
  const router = useRouter()
  const { activeTenantId } = useAuth()
  const setup = useSetupState({ enabled: !!activeTenantId })
  const { complete } = useSetupStep()
  const saved = setup.tenant?.agent_settings

  const [language, setLanguage] = React.useState<Language | null>(null)
  const [tone, setTone] = React.useState<Tone | null>(null)
  const [greeting, setGreeting] = React.useState<string | null>(null)
  const [refund, setRefund] = React.useState<boolean | null>(null)
  const [complaint, setComplaint] = React.useState<boolean | null>(null)
  const [human, setHuman] = React.useState<boolean | null>(null)
  const [largeOn, setLargeOn] = React.useState<boolean | null>(null)
  const [largeAmount, setLargeAmount] = React.useState<number | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [saving, setSaving] = React.useState(false)

  const shownLanguage: Language = language ?? saved?.language ?? "match"
  const shownTone: Tone = tone ?? saved?.tone ?? "warm"
  const restaurantName = setup.tenant?.business_name ?? ""
  const suggestion = suggestedGreeting(restaurantName, shownLanguage)
  const savedGreeting = saved?.greeting ?? null
  const shownGreeting = greeting ?? savedGreeting ?? suggestion
  const edited = greeting !== null && greeting !== suggestion
  const escalate = saved?.escalate_on
  const shownRefund = refund ?? escalate?.refund ?? true
  const shownComplaint = complaint ?? escalate?.complaint ?? true
  const shownHuman = human ?? escalate?.human_requested ?? true
  const savedLarge = escalate?.large_order_over ?? null
  const shownLargeOn = largeOn ?? savedLarge !== null
  const shownLargeAmount = largeAmount ?? savedLarge ?? 5000
  const currency = setup.tenant?.currency ?? "USD"

  async function save() {
    if (saving) return
    setSaving(true)
    setError(null)
    try {
      await saveAgentSettings({
        language: shownLanguage,
        tone: shownTone,
        greeting: edited || savedGreeting ? shownGreeting.trim() || null : null,
        escalate_on: {
          refund: shownRefund,
          complaint: shownComplaint,
          human_requested: shownHuman,
          large_order_over: shownLargeOn ? shownLargeAmount : null,
        },
      })
      await complete.mutateAsync({ step: "agent", action: "complete" })
      router.push("/setup/test")
    } catch (err) {
      setError(errorDetail(err, "Could not save the agent settings. Try again."))
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <div className="space-y-1.5">
        <DialogTitle className="font-heading text-lg">Set up your agent</DialogTitle>
        <DialogDescription>How it talks to your customers, and what it hands to you.</DialogDescription>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="a-lang">Reply language</Label>
          <select
            id="a-lang"
            value={shownLanguage}
            onChange={(e) => setLanguage(e.target.value as Language)}
            className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"
          >
            {LANGUAGES.map((l) => (
              <option key={l.value} value={l.value}>{l.label}</option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="a-tone">Tone</Label>
          <select
            id="a-tone"
            value={shownTone}
            onChange={(e) => setTone(e.target.value as Tone)}
            className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"
          >
            {TONES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <Label htmlFor="a-greet">Greeting</Label>
          {edited && (
            <button
              type="button"
              className="text-xs text-muted-foreground underline underline-offset-3 hover:text-foreground"
              onClick={() => setGreeting(null)}
            >
              Reset to suggested
            </button>
          )}
        </div>
        <Textarea
          id="a-greet"
          rows={2}
          value={shownGreeting}
          onChange={(e) => setGreeting(e.target.value)}
        />
      </div>

      <fieldset className="space-y-3">
        <legend className="mb-1 text-sm font-medium">Always send to me</legend>
        <ToggleRow label="Refund requests" checked={shownRefund} onChange={setRefund} />
        <ToggleRow label="Complaints" checked={shownComplaint} onChange={setComplaint} />
        <ToggleRow label="Customer asks for a person" checked={shownHuman} onChange={setHuman} />
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Switch checked={shownLargeOn} onCheckedChange={(on: boolean) => setLargeOn(on)} aria-label="Large orders" />
            <span className="text-sm">Orders over</span>
          </div>
          {shownLargeOn && (
            <div className="flex items-center gap-2">
              <Input
                type="number"
                min={0}
                className="w-28"
                value={shownLargeAmount}
                onChange={(e) => setLargeAmount(Number(e.target.value))}
                aria-label="Order amount"
              />
              <span className="font-mono text-[12px] text-muted-foreground">{currency}</span>
            </div>
          )}
        </div>
      </fieldset>

      <StepError message={error} />

      <DialogFooter>
        <Button variant="outline" onClick={() => router.push("/setup/hours")} disabled={saving}>
          Back
        </Button>
        <Button onClick={save} disabled={saving}>
          {saving ? "Saving..." : "Continue"}
        </Button>
      </DialogFooter>
    </>
  )
}

function ToggleRow({
  label,
  checked,
  onChange,
}: {
  label: string
  checked: boolean
  onChange: (value: boolean) => void
}) {
  return (
    <div className="flex items-center gap-3">
      <Switch checked={checked} onCheckedChange={(on: boolean) => onChange(on)} aria-label={label} />
      <span className="text-sm">{label}</span>
    </div>
  )
}
