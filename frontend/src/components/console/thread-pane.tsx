"use client"

import * as React from "react"
import { SendIcon } from "lucide-react"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import { AgentTraceLine } from "@/components/console/agent-trace-line"
import { MessageTicks } from "@/components/console/message-ticks"
import { TypingIndicator } from "@/components/console/typing-indicator"
import { TakeoverBar } from "@/components/console/takeover-bar"
import { QuickReplies } from "@/components/console/quick-replies"
import { USE_MOCKS } from "@/lib/mocks"
import type { MockConversation } from "@/lib/mock/conversations"
import type { MockMessage } from "@/lib/mock/messages"

function initials(name: string) {
  return (
    name
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((n) => n[0]?.toUpperCase())
      .join("") || "?"
  )
}

export function ThreadPane({
  conversation,
  messages,
  isLoading,
  isSending,
  onSend,
  onToggleTakeover,
  onResolveEscalation,
}: {
  conversation: MockConversation | null
  messages: MockMessage[]
  isLoading: boolean
  isSending: boolean
  onSend: (text: string) => void
  onToggleTakeover: () => void
  onResolveEscalation: () => void
}) {
  const [draft, setDraft] = React.useState("")
  const scrollRef = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [messages, conversation?.isAgentTyping])

  if (!conversation) {
    return (
      <div className="flex min-w-0 flex-1 items-center justify-center bg-muted/30">
        <p className="font-mono text-xs text-muted-foreground">
          Select a conversation from the queue to see the thread.
        </p>
      </div>
    )
  }

  // Takeover is a mock-only prototype feature (owner roadmap #1 — no
  // backend flag exists yet), so it only gates the composer in mock mode.
  // In real mode the owner can always reply manually, same as before.
  const composerDisabled =
    conversation.status === "closed" || (USE_MOCKS && !conversation.takeoverByOwner)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const text = draft.trim()
    if (!text) return
    onSend(text)
    setDraft("")
  }

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <header className="flex shrink-0 items-center gap-3 border-b border-border bg-card px-4 py-3">
        <Avatar className="size-9">
          <AvatarFallback>{initials(conversation.customer_name)}</AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{conversation.customer_name}</p>
          <p className="truncate text-xs text-muted-foreground">{conversation.customer_phone}</p>
        </div>
        <TakeoverBar
          conversation={conversation}
          onToggle={onToggleTakeover}
          onResolveEscalation={onResolveEscalation}
        />
      </header>

      <div ref={scrollRef} className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto bg-muted/30 p-4">
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className={cn("h-10 w-2/3 rounded-[12px]", i % 2 === 1 && "ml-auto")} />
            ))}
          </div>
        ) : messages.length === 0 ? (
          <div className="flex flex-1 items-center justify-center">
            <p className="font-mono text-xs text-muted-foreground">No messages in this conversation yet.</p>
          </div>
        ) : (
          messages.map((message) => {
            const isCustomer = message.sender === "customer"
            const isAgent = message.sender === "agent"
            const isSystem = message.sender === "system"

            if (isSystem) {
              return (
                <div key={message.message_id} className="flex justify-center">
                  <span className="rounded border border-dashed border-border px-2 py-1 font-mono text-[11px] text-muted-foreground">
                    {message.content}
                  </span>
                </div>
              )
            }

            return (
              <div key={message.message_id} className="flex flex-col gap-1">
                <div className={cn("flex w-full items-end gap-2", isCustomer ? "justify-start" : "justify-end")}>
                  {isCustomer && (
                    <Avatar className="size-6 shrink-0">
                      <AvatarFallback className="text-[10px]">
                        {initials(conversation.customer_name)}
                      </AvatarFallback>
                    </Avatar>
                  )}
                  <div
                    className={cn(
                      "flex max-w-[75%] flex-col gap-1 rounded-[12px] px-3 py-2 text-sm",
                      isCustomer && "rounded-bl-[4px] bg-card",
                      isAgent && "rounded-br-[4px] bg-ai-soft",
                      !isCustomer && !isAgent && "rounded-br-[4px] bg-new-soft"
                    )}
                  >
                    {!isCustomer && (
                      <span className="font-mono text-[10px] tracking-wide text-muted-foreground uppercase">
                        {isAgent ? "Agent" : "You"}
                      </span>
                    )}
                    <p className="whitespace-pre-wrap leading-snug">{message.content}</p>
                    <div className="flex items-center justify-end gap-1">
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {new Date(message.created_at).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                      {!isCustomer && <MessageTicks status={message.status} />}
                    </div>
                  </div>
                </div>
                {message.trace?.map((step, i) => (
                  <AgentTraceLine key={i} step={step} />
                ))}
              </div>
            )
          })
        )}
        {conversation.isAgentTyping && <TypingIndicator />}
      </div>

      {conversation.escalated && !conversation.takeoverByOwner && (
        <QuickReplies onPick={(text) => onSend(text)} />
      )}

      <form onSubmit={handleSubmit} className="flex shrink-0 items-center gap-2 border-t border-border bg-card p-3">
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={composerDisabled ? "The agent is replying. Take over to type." : "Type a message..."}
          disabled={composerDisabled || isSending}
          className="flex-1"
        />
        <Button type="submit" size="icon" disabled={composerDisabled || !draft.trim() || isSending}>
          <SendIcon className="size-4" />
          <span className="sr-only">Send</span>
        </Button>
      </form>
    </div>
  )
}
