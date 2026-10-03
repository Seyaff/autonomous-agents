"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { CheckIcon, SendIcon, WrenchIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DialogDescription, DialogFooter, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { useAuth } from "@/components/providers/auth-provider"
import { useSetupState } from "@/hooks/setup/use-setup-state"
import { useSetupStep } from "@/hooks/setup/use-setup-step"
import { useTestChat } from "@/hooks/setup/use-test-chat"
import type { TestChatMessage } from "@/services/setup/setup.service"
import { cn } from "@/lib/utils"

const SAMPLES = [
  { label: "Say hello", text: "Salam" },
  { label: "Ask about the menu", text: "menu mein kya kya hai?" },
  { label: "Opening hours", text: "kab tak khula hai?" },
  { label: "Delivery", text: "delivery hoti hai? kahan tak?" },
  { label: "Test order", text: "2 burger bhej do, Gulberg 3, cash on delivery" },
  { label: "Complaint", text: "mera order bohat late aaya, ye complaint hai" },
]

export function TestStep() {
  const router = useRouter()
  const { activeTenantId } = useAuth()
  const setup = useSetupState({ enabled: !!activeTenantId })
  const { complete } = useSetupStep()
  const { transcript, send, reset } = useTestChat()

  const [draft, setDraft] = React.useState("")
  const [tried, setTried] = React.useState<Set<string>>(new Set())
  const scrollRef = React.useRef<HTMLDivElement>(null)

  const name = setup.tenant?.business_name ?? "Your restaurant"
  const initial = name.trim().charAt(0).toUpperCase() || "S"
  const messages: TestChatMessage[] = transcript.data ?? []

  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [messages.length, send.isPending])

  function sendText(text: string) {
    const clean = text.trim()
    if (!clean || send.isPending) return
    send.mutate(clean, {
      onSuccess: () => setDraft(""),
    })
  }

  return (
    <>
      <div className="space-y-1.5">
        <DialogTitle className="font-heading text-lg">Test your agent</DialogTitle>
        <DialogDescription>
          Chat with your agent as a customer would. Nothing here reaches a real customer or changes an order.
        </DialogDescription>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_220px]">
        <div className="flex min-h-[360px] flex-col overflow-hidden rounded-lg border border-border">
          <div className="flex items-center justify-between gap-3 border-b border-border bg-card px-3 py-2">
            <div className="flex items-center gap-2">
              <span className="flex size-7 items-center justify-center rounded-full bg-muted font-heading text-sm">
                {initial}
              </span>
              <span className="text-sm font-medium">{name}</span>
              <Badge variant="outline">Test mode</Badge>
            </div>
            <Button
              size="xs"
              variant="ghost"
              disabled={reset.isPending}
              onClick={() => {
                setTried(new Set())
                reset.mutate()
              }}
            >
              Reset chat
            </Button>
          </div>

          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-3">
            {messages.length === 0 && !transcript.isLoading && (
              <AgentBubble>Salam! {name} mein khush amdeed. Kya order krna hai?</AgentBubble>
            )}
            {messages.map((m, i) =>
              m.role === "customer" ? (
                <div key={i} className="flex justify-end">
                  <div className="max-w-[80%] rounded-xl rounded-br-sm bg-primary px-3 py-2 text-sm text-primary-foreground">
                    {m.content}
                  </div>
                </div>
              ) : (
                <div key={i} className="space-y-1">
                  {(m.trace ?? []).map((t, j) => (
                    <p key={j} className="flex items-center gap-1.5 font-mono text-[12px] text-ai">
                      <WrenchIcon className="size-3" />
                      ↳ {t.tool}({Object.values(t.args ?? {}).map(String).join(", ")}) → {t.result_summary.slice(0, 90)}
                    </p>
                  ))}
                  <AgentBubble>{m.content}</AgentBubble>
                  {m.escalated && <Badge variant="destructive">Sent to you under Needs you</Badge>}
                </div>
              )
            )}
            {send.isPending && (
              <p className="font-mono text-[12px] text-muted-foreground">Agent is typing...</p>
            )}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault()
              sendText(draft)
            }}
            className="flex gap-2 border-t border-border p-3"
          >
            <Input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Type as a customer..."
              disabled={send.isPending}
            />
            <Button type="submit" size="icon" disabled={send.isPending || !draft.trim()} aria-label="Send">
              <SendIcon className="size-4" />
            </Button>
          </form>
        </div>

        <div className="space-y-2">
          <p className="font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
            Try these · {tried.size}/{SAMPLES.length}
          </p>
          {SAMPLES.map((s) => {
            const done = tried.has(s.label)
            return (
              <button
                key={s.label}
                type="button"
                disabled={send.isPending}
                onClick={() => {
                  setTried((prev) => new Set(prev).add(s.label))
                  sendText(s.text)
                }}
                className={cn(
                  "flex w-full items-center justify-between gap-2 rounded-md border px-3 py-2 text-left text-sm hover:bg-muted disabled:opacity-60",
                  done ? "border-ok/40 text-ok" : "border-border"
                )}
              >
                {s.label}
                {done && <CheckIcon className="size-4" />}
              </button>
            )
          })}
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" onClick={() => router.push("/setup/agent")}>
          Back
        </Button>
        <Button
          onClick={() => complete.mutate({ step: "test", action: "complete" }, { onSuccess: () => router.push("/setup/whatsapp") })}
          disabled={complete.isPending}
        >
          Continue
        </Button>
      </DialogFooter>
    </>
  )
}

function AgentBubble({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] rounded-xl rounded-bl-sm bg-ai-soft px-3 py-2 text-sm">
        <span className="mb-0.5 block font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">Agent</span>
        <span className="whitespace-pre-wrap">{children}</span>
      </div>
    </div>
  )
}
