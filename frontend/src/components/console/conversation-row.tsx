"use client"

import { cn } from "@/lib/utils"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { StatusChip, type ChipTone } from "@/components/console/status-chip"
import type { MockConversation } from "@/lib/mock/conversations"

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

function relativeTime(iso: string) {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60_000)
  if (minutes < 1) return "now"
  if (minutes < 60) return `${minutes}m`
  return `${Math.round(minutes / 60)}h`
}

function statusFor(
  conversation: Pick<MockConversation, "status" | "escalated" | "takeoverByOwner">
): { label: string; tone: ChipTone } {
  if (conversation.status === "closed") return { label: "Resolved", tone: "ok" }
  if (conversation.escalated) return { label: "Needs you", tone: "need" }
  if (conversation.takeoverByOwner) return { label: "You're replying", tone: "new" }
  return { label: "Agent replying", tone: "ai" }
}

export function ConversationRow({
  conversation,
  selected,
  flash,
  onSelect,
}: {
  conversation: MockConversation
  selected: boolean
  flash?: boolean
  onSelect: () => void
}) {
  const chip = statusFor(conversation)

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "flex w-full items-start gap-2.5 border-l-[3px] border-transparent px-3 py-2.5 text-left transition-colors",
        selected ? "border-l-primary bg-muted" : "hover:bg-muted/60",
        flash && "motion-safe:animate-[flash-ai_1s_ease-out]"
      )}
    >
      <Avatar className="size-8 shrink-0">
        <AvatarFallback className="text-xs">{initials(conversation.customer_name)}</AvatarFallback>
      </Avatar>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium">{conversation.customer_name}</span>
          <span className="ml-auto shrink-0 font-mono text-[10px] text-muted-foreground">
            {relativeTime(conversation.last_activity_at)}
          </span>
        </div>
        <p
          className={cn(
            "truncate text-xs",
            conversation.isAgentTyping ? "italic text-ai" : "text-muted-foreground"
          )}
        >
          {conversation.isAgentTyping ? "typing…" : conversation.last_message?.content ?? "No messages yet"}
        </p>
        <div className="mt-1 flex items-center gap-1.5">
          <StatusChip tone={chip.tone} label={chip.label} />
          {conversation.unread_count > 0 && (
            <span className="ml-auto rounded-full bg-primary px-1.5 py-0 font-mono text-[10px] text-primary-foreground">
              {conversation.unread_count}
            </span>
          )}
        </div>
      </div>
    </button>
  )
}
