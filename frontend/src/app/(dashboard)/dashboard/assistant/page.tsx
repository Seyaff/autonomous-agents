"use client"

import * as React from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import {
  loadAssistantHistory,
  streamAssistantTurn,
  type AssistantChange,
  type AssistantEvent,
  type AssistantMessage,
} from "@/services/tenant/assistant.service"

// Short labels for what the assistant is doing while it works.
const TOOL_STEPS: Record<string, string> = {
  get_restaurant_settings: "Reading your settings",
  update_restaurant_settings: "Saving restaurant settings",
  update_reply_settings: "Saving reply settings",
  set_agent_enabled: "Updating the agent",
  list_menu: "Checking the menu",
  set_dish_sold_out: "Updating the menu",
}

const FIELD_LABELS: Record<string, string> = {
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

const EXAMPLES = [
  "Close on Fridays, open 12 to 11 on other days",
  "Set the delivery fee to Rs 150",
  "Reply in Roman Urdu with a friendly tone",
  "Mark Chicken Karahi as sold out",
]

type ChatMessage = AssistantMessage & { streaming?: boolean; tools?: string[]; changes?: AssistantChange[] }

function fieldLabel(field: string): string {
  if (FIELD_LABELS[field]) return FIELD_LABELS[field]
  if (field.startsWith("agent_settings.")) return `Reply: ${field.slice("agent_settings.".length).replace(/_/g, " ")}`
  return field
}

function showValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "none"
  if (typeof value === "boolean") return value ? "on" : "off"
  if (Array.isArray(value)) {
    if (value.length === 7 && value.every((v) => typeof v === "object" && v !== null && "day" in v)) return "7-day hours"
    return value.length ? value.map(String).join(", ") : "none"
  }
  if (typeof value === "object") return JSON.stringify(value)
  return String(value)
}

export default function AssistantPage() {
  const queryClient = useQueryClient()
  const history = useQuery({ queryKey: ["assistant", "history"], queryFn: loadAssistantHistory })
  // The saved conversation is shown until the owner sends something; after that this holds the live chat.
  const [live, setLive] = React.useState<ChatMessage[] | null>(null)
  const messages = React.useMemo<ChatMessage[]>(() => live ?? history.data ?? [], [live, history.data])
  const setMessages = (update: (prev: ChatMessage[]) => ChatMessage[]) =>
    setLive((prev) => update(prev ?? history.data ?? []))
  const [input, setInput] = React.useState("")
  const [sending, setSending] = React.useState(false)
  const bottom = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [messages])

  // Updates the reply that is being streamed, which is always the last message.
  const patchLast = (update: (m: ChatMessage) => ChatMessage) =>
    setMessages((prev) => (prev.length ? [...prev.slice(0, -1), update(prev[prev.length - 1])] : prev))

  const send = async (text: string) => {
    const message = text.trim()
    if (!message || sending) return
    setInput("")
    setSending(true)
    setMessages((prev) => [
      ...prev,
      { role: "owner", content: message },
      { role: "assistant", content: "", streaming: true, tools: [], changes: [] },
    ])
    let savedChanges = 0
    try {
      await streamAssistantTurn(message, (event: AssistantEvent) => {
        if (event.type === "token") patchLast((m) => ({ ...m, content: m.content + event.text }))
        else if (event.type === "tool") patchLast((m) => ({ ...m, tools: [...(m.tools ?? []), event.name] }))
        else if (event.type === "change") {
          savedChanges += 1
          patchLast((m) => ({ ...m, changes: [...(m.changes ?? []), event.change] }))
        } else if (event.type === "error") patchLast((m) => ({ ...m, content: event.message }))
        else if (event.type === "done") patchLast((m) => ({ ...m, content: m.content || event.reply }))
      })
      if (savedChanges) {
        toast.success(`Saved ${savedChanges} change${savedChanges === 1 ? "" : "s"}.`)
        queryClient.invalidateQueries()
      }
    } catch (err) {
      const text = err instanceof Error ? err.message : "The assistant couldn't do that. Try again."
      patchLast((m) => ({ ...m, content: text }))
    } finally {
      patchLast((m) => ({ ...m, streaming: false }))
      setSending(false)
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 border-b border-border bg-card px-4 py-2">
        <h1 className="text-sm font-medium">Assistant</h1>
        <p className="font-mono text-[11px] text-muted-foreground">
          Tell it what to change. It updates your settings, menu and replies, and shows what it changed.
        </p>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="mx-auto max-w-md space-y-3 pt-8 text-center">
            <p className="text-sm text-muted-foreground">Try one of these, or type your own.</p>
            <div className="flex flex-wrap justify-center gap-2">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => send(ex)}
                  className="rounded-full border border-border px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={m.role === "owner" ? "flex justify-end" : "flex justify-start"}>
            <div className={m.role === "owner" ? "max-w-[80%] space-y-2 text-right" : "max-w-[80%] space-y-2"}>
              {m.role === "assistant" && m.tools && m.tools.length > 0 && (
                <ul className="space-y-0.5 font-mono text-[11px] text-muted-foreground">
                  {m.tools.map((t, j) => (
                    <li key={j}>{TOOL_STEPS[t] ?? t}…</li>
                  ))}
                </ul>
              )}
              {(m.content || m.streaming) && (
                <div
                  className={
                    "inline-block whitespace-pre-wrap rounded-lg px-3 py-2 text-left text-sm " +
                    (m.role === "owner" ? "bg-primary text-primary-foreground" : "bg-muted text-foreground")
                  }
                >
                  {m.content}
                  {m.streaming && <span className="ml-0.5 animate-pulse">▍</span>}
                </div>
              )}
              {m.changes && m.changes.length > 0 && (
                <ul className="space-y-0.5 text-left font-mono text-[11px] text-muted-foreground">
                  {m.changes.map((c, j) => (
                    <li key={j}>
                      {fieldLabel(c.field)}: {showValue(c.before)} → {showValue(c.after)}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        ))}
        <div ref={bottom} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          send(input)
        }}
        className="shrink-0 border-t border-border bg-card p-3"
      >
        <div className="flex items-end gap-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault()
                send(input)
              }
            }}
            placeholder="Describe a change, e.g. close on Fridays and set delivery to Rs 150"
            maxLength={2000}
            rows={2}
            disabled={sending}
            className="min-h-0 resize-none"
          />
          <Button type="submit" disabled={sending || !input.trim()}>
            {sending ? "Working…" : "Send"}
          </Button>
        </div>
      </form>
    </div>
  )
}
