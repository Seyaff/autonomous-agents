"use client"

import * as React from "react"
import { useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { askSettingsAssistant, type AssistantChange, type AssistantTurn } from "@/services/tenant/assistant.service"

const LABELS: Record<string, string> = {
  business_name: "Name",
  business_phone: "Phone",
  address: "Address",
  currency: "Currency",
  timezone: "Timezone",
  "delivery_settings.flat_delivery_fee": "Delivery fee",
  "delivery_settings.avg_prep_time_minutes": "Prep time",
  min_order_amount: "Minimum order",
  operating_hours: "Opening hours",
  delivery_areas: "Delivery areas",
  payment_methods: "Payment methods",
  order_types: "Order types",
  agent_enabled: "Agent on/off",
  "menu.sold_out": "Sold out today",
}

function label(field: string): string {
  if (LABELS[field]) return LABELS[field]
  if (field.startsWith("agent_settings.")) return `Reply: ${field.slice("agent_settings.".length).replace("_", " ")}`
  return field
}

function show(value: unknown): string {
  if (value === null || value === undefined || value === "") return "none"
  if (typeof value === "boolean") return value ? "on" : "off"
  if (Array.isArray(value)) {
    if (value.length === 7 && value.every((v) => typeof v === "object" && v !== null && "day" in v)) {
      return "7-day hours"
    }
    return value.length ? value.join(", ") : "none"
  }
  if (typeof value === "object") return JSON.stringify(value)
  return String(value)
}

function errorText(err: unknown, fallback: string) {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback
}

const EXAMPLES = ["Close on Fridays", "Delivery fee Rs 150", "Reply in Roman Urdu, friendly tone", "Mark Chicken Karahi sold out"]

export function SettingsAssistant() {
  const queryClient = useQueryClient()
  const [turns, setTurns] = React.useState<AssistantTurn[]>([])
  const [changes, setChanges] = React.useState<Record<number, AssistantChange[]>>({})
  const [input, setInput] = React.useState("")
  const [sending, setSending] = React.useState(false)

  const send = async (text: string) => {
    const message = text.trim()
    if (!message || sending) return
    const history = turns.slice(-20)
    setTurns((prev) => [...prev, { role: "owner", content: message }])
    setInput("")
    setSending(true)
    try {
      const res = await askSettingsAssistant(message, history)
      setTurns((prev) => {
        const next = [...prev, { role: "assistant" as const, content: res.reply }]
        if (res.changes.length) setChanges((c) => ({ ...c, [next.length - 1]: res.changes }))
        return next
      })
      if (res.changes.length) {
        toast.success(`Saved ${res.changes.length} change${res.changes.length === 1 ? "" : "s"}.`)
        queryClient.invalidateQueries()
      }
    } catch (err) {
      toast.error(errorText(err, "The assistant couldn't do that. Try again."))
    } finally {
      setSending(false)
    }
  }

  return (
    <section className="rounded-lg border border-border bg-card p-4 space-y-3">
      <div>
        <h2 className="text-sm font-medium">Assistant</h2>
        <p className="font-mono text-[11px] text-muted-foreground">
          Describe what to change. It updates the settings and tells you what it changed.
        </p>
      </div>

      {turns.length > 0 && (
        <div className="max-h-80 space-y-3 overflow-y-auto">
          {turns.map((t, i) => (
            <div key={i} className={t.role === "owner" ? "text-right" : "text-left"}>
              <div
                className={
                  "inline-block max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm " +
                  (t.role === "owner" ? "bg-primary text-primary-foreground" : "bg-muted text-foreground")
                }
              >
                {t.content}
              </div>
              {changes[i]?.length ? (
                <ul className="mt-1 space-y-0.5 text-left font-mono text-[11px] text-muted-foreground">
                  {changes[i].map((c, j) => (
                    <li key={j}>
                      {label(c.field)}: {show(c.before)} → {show(c.after)}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ))}
        </div>
      )}

      {turns.length === 0 && (
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => send(ex)}
              className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground hover:text-foreground"
            >
              {ex}
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault()
          send(input)
        }}
        className="flex gap-2"
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. Close on Fridays and set delivery to Rs 150"
          maxLength={2000}
          disabled={sending}
        />
        <Button type="submit" disabled={sending || !input.trim()}>
          {sending ? "Working…" : "Send"}
        </Button>
      </form>
    </section>
  )
}
