"use client"

import { Button } from "@/components/ui/button"
import { StatusChip, type ChipTone } from "@/components/console/status-chip"
import type { MockConversation } from "@/lib/mock/conversations"

export function TakeoverBar({
  conversation,
  onToggle,
  onResolveEscalation,
}: {
  conversation: Pick<MockConversation, "status" | "escalated" | "takeoverByOwner">
  onToggle: () => void
  onResolveEscalation: () => void
}) {
  const chip: { tone: ChipTone; label: string } =
    conversation.status === "closed"
      ? { tone: "ok", label: "Resolved" }
      : conversation.takeoverByOwner
        ? { tone: "new", label: "You're replying" }
        : conversation.escalated
          ? { tone: "need", label: "Needs you" }
          : { tone: "ai", label: "Agent replying" }

  return (
    <div className="flex items-center gap-2">
      <StatusChip tone={chip.tone} label={chip.label} />
      {conversation.status !== "closed" && (
        <Button variant="outline" size="xs" onClick={onToggle}>
          {conversation.takeoverByOwner ? "Hand back to agent" : "Take over"}
        </Button>
      )}
      {conversation.escalated && conversation.status !== "closed" && (
        <Button variant="ghost" size="xs" onClick={onResolveEscalation}>
          Mark handled
        </Button>
      )}
    </div>
  )
}
