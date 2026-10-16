"use client"

import * as React from "react"
import { ArrowUpIcon, CheckIcon, CircleIcon, SquareIcon } from "lucide-react"
import { cn } from "cn"

import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { ThinkingIndicator } from "@/components/assistant/thinking-indicator"
import { useAssistant, type ChatMessage } from "@/components/assistant/assistant-provider"
import { toolStep } from "@/lib/agent-words"
import type { AssistantAction, AssistantChange } from "@/services/tenant/assistant.service"

export const SUGGESTIONS = [
  "How did we do today?",
  "Which chats need me right now?",
  "Show this week's best sellers",
  "Which customers haven't come back in a month?",
  "Close on Fridays, open 12 to 11 other days",
  "Reply to customers in a friendlier tone",
]

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
  business_description: "Business description",
  "menu.sold_out": "Unavailable today",
  "menu.added": "Catalog: added",
  "menu.removed": "Catalog: removed",
  "chat.handled_by": "Chat handled by",
  "chat.needs_you": "Needs you cleared",
}

function fieldLabel(field: string): string {
  if (FIELD_LABELS[field]) return FIELD_LABELS[field]
  if (field.startsWith("agent_settings.")) return `Reply: ${field.slice("agent_settings.".length).replace(/_/g, " ")}`
  if (field.startsWith("order.")) return `Order ${field.slice("order.".length)}`
  if (field.startsWith("menu.")) return `Catalog ${field.slice("menu.".length)}`
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
  const text = String(value)
  return text.length > 80 ? `${text.slice(0, 77)}…` : text
}

/** **bold** inside a line. */
function Inline({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return (
    <>
      {parts.map((p, i) =>
        p.startsWith("**") && p.endsWith("**") && p.length > 4 ? (
          <strong key={i} className="font-semibold">
            {p.slice(2, -2)}
          </strong>
        ) : (
          <React.Fragment key={i}>{p}</React.Fragment>
        ),
      )}
    </>
  )
}

/** The agent writes plain text with "- " lists. */
function RichText({ text }: { text: string }) {
  const lines = text.split("\n")
  return (
    <div className="space-y-1">
      {lines.map((line, i) => {
        const bullet = line.match(/^\s*[-*•]\s+(.*)$/)
        if (bullet)
          return (
            <div key={i} className="flex gap-2 pl-1">
              <span className="text-muted-foreground">•</span>
              <span className="min-w-0">
                <Inline text={bullet[1]} />
              </span>
            </div>
          )
        if (!line.trim()) return <div key={i} className="h-1" />
        return (
          <p key={i}>
            <Inline text={line} />
          </p>
        )
      })}
    </div>
  )
}

function Changes({ changes }: { changes: AssistantChange[] }) {
  return (
    <ul className="space-y-0.5 rounded-md border border-border bg-muted/40 px-2.5 py-1.5 font-mono text-[11px] text-muted-foreground">
      {changes.map((c, j) => (
        <li key={j} className="flex gap-1.5">
          <CheckIcon className="mt-0.5 size-3 shrink-0 text-ai" />
          <span>
            {fieldLabel(c.field)}: {showValue(c.before)} → <span className="text-foreground">{showValue(c.after)}</span>
          </span>
        </li>
      ))}
    </ul>
  )
}

const ACTION_STATUS: Record<AssistantAction["status"], string> = {
  pending: "",
  done: "Done",
  failed: "Didn't go through",
  cancelled: "Cancelled",
  expired: "Expired",
}

function ActionCard({ action }: { action: AssistantAction }) {
  const { decide } = useAssistant()
  const [busy, setBusy] = React.useState<"confirm" | "cancel" | null>(null)
  const pending = action.status === "pending"

  const press = async (confirm: boolean) => {
    setBusy(confirm ? "confirm" : "cancel")
    await decide(action, confirm)
    setBusy(null)
  }

  return (
    <div className={cn("rounded-lg border bg-card p-3 text-sm shadow-xs", pending ? "border-ai/50" : "border-border opacity-80")}>
      <p className="font-medium">{action.summary}</p>
      {action.detail && (
        <p className="mt-1 line-clamp-6 whitespace-pre-wrap rounded bg-muted/60 px-2 py-1.5 text-[13px] text-muted-foreground">
          {action.detail}
        </p>
      )}
      {pending ? (
        <div className="mt-2.5 flex gap-2">
          <Button size="sm" onClick={() => press(true)} disabled={busy !== null}>
            {busy === "confirm" ? "Working…" : action.confirm_label || "Confirm"}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => press(false)} disabled={busy !== null}>
            Cancel
          </Button>
        </div>
      ) : (
        <p className="mt-2 font-mono text-[11px] text-muted-foreground">{ACTION_STATUS[action.status] ?? action.status}</p>
      )}
    </div>
  )
}

function Steps({ message }: { message: ChatMessage }) {
  const done = (message.steps ?? []).filter((s) => s.done)
  if (!done.length) return null
  return (
    <ul className="space-y-0.5 text-[12px] text-muted-foreground">
      {done.map((s) => (
        <li key={s.id} className="flex items-center gap-1.5" style={{ animation: "agent-word-in 200ms ease-out" }}>
          <CircleIcon className="size-1.5 fill-current text-ai" />
          {toolStep(s.name, true)}
        </li>
      ))}
    </ul>
  )
}

function Message({ message }: { message: ChatMessage }) {
  if (message.role === "owner") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-primary px-3 py-2 text-sm text-primary-foreground">
          {message.content}
        </div>
      </div>
    )
  }
  const thinking = message.streaming && (!message.content.trim() || (message.steps ?? []).some((s) => !s.done))
  return (
    <div className="space-y-2">
      <Steps message={message} />
      {message.content.trim() && (
        <div className="text-sm leading-relaxed text-foreground">
          <RichText text={message.content.trim()} />
          {message.streaming && !thinking && <span className="ml-0.5 inline-block animate-pulse text-ai">▍</span>}
        </div>
      )}
      {thinking && <ThinkingIndicator steps={message.steps ?? []} />}
      {message.changes && message.changes.length > 0 && <Changes changes={message.changes} />}
      {message.actions?.map((a) => <ActionCard key={a.action_id} action={a} />)}
    </div>
  )
}

export function AssistantChat({ autoFocus = false, className }: { autoFocus?: boolean; className?: string }) {
  const { messages, loading, sending, send, stop } = useAssistant()
  const [input, setInput] = React.useState("")
  const scroller = React.useRef<HTMLDivElement>(null)
  const box = React.useRef<HTMLTextAreaElement>(null)

  React.useEffect(() => {
    const el = scroller.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" })
  }, [messages])

  React.useEffect(() => {
    if (autoFocus) box.current?.focus()
  }, [autoFocus])

  const submit = (text: string) => {
    if (!text.trim() || sending) return
    setInput("")
    void send(text)
  }

  return (
    <div className={cn("flex min-h-0 flex-1 flex-col", className)}>
      <div ref={scroller} className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4">
        {!loading && messages.length === 0 && (
          <div className="space-y-4 pt-6">
            <div className="space-y-1">
              <p className="text-base font-medium">What should we get done?</p>
              <p className="text-sm text-muted-foreground">
                Ask about sales, orders or chats, or tell me what to change. Anything that reaches customers waits for your
                OK.
              </p>
            </div>
            <div className="flex flex-col items-start gap-1.5">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => submit(s)}
                  className="rounded-md px-2 py-1 text-left text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <Message key={i} message={m} />
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          submit(input)
        }}
        className="shrink-0 border-t border-border p-3"
      >
        <div className="relative rounded-xl border border-border bg-background focus-within:border-ai/60 focus-within:ring-2 focus-within:ring-ai/15">
          <Textarea
            ref={box}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault()
                submit(input)
              }
            }}
            placeholder={sending ? "Working on it…" : "Ask anything or say what to change"}
            maxLength={2000}
            rows={2}
            className="max-h-40 min-h-0 resize-none border-0 bg-transparent pr-12 shadow-none focus-visible:ring-0"
          />
          {sending ? (
            <Button type="button" size="icon-sm" variant="secondary" onClick={stop} className="absolute right-2 bottom-2" aria-label="Stop">
              <SquareIcon className="size-3 fill-current" />
            </Button>
          ) : (
            <Button type="submit" size="icon-sm" disabled={!input.trim()} className="absolute right-2 bottom-2" aria-label="Send">
              <ArrowUpIcon className="size-4" />
            </Button>
          )}
        </div>
      </form>
    </div>
  )
}
