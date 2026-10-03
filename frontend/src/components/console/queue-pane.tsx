"use client"

import { ConversationRow } from "@/components/console/conversation-row"
import { Skeleton } from "@/components/ui/skeleton"
import type { QueueGroups } from "@/hooks/console/use-queue"

const GROUP_ORDER: (keyof QueueGroups)[] = ["needs_you", "owner_handling", "agent_handling", "resolved"]
const GROUP_LABELS: Record<keyof QueueGroups, string> = {
  needs_you: "Needs you",
  owner_handling: "You're handling",
  agent_handling: "Agent handling",
  resolved: "Resolved today",
}

export function QueuePane({
  groups,
  isLoading,
  selectedId,
  onSelect,
}: {
  groups: QueueGroups
  isLoading: boolean
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  const total = GROUP_ORDER.reduce((n, key) => n + groups[key].length, 0)

  return (
    <div className="flex h-full w-full shrink-0 flex-col overflow-y-auto border-r border-border bg-card md:w-[300px]">
      {isLoading ? (
        <div className="space-y-3 p-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : total === 0 ? (
        <div className="flex h-full items-center justify-center p-6 text-center">
          <p className="font-mono text-xs text-muted-foreground">
            No conversations yet. They&apos;ll show up here once customers message you on WhatsApp.
          </p>
        </div>
      ) : (
        GROUP_ORDER.map((key) => {
          const items = groups[key]
          if (items.length === 0) return null
          return (
            <div key={key}>
              <p className="sticky top-0 z-10 bg-card px-3 pt-3 pb-1 font-mono text-[11px] tracking-[.08em] text-muted-foreground uppercase">
                {GROUP_LABELS[key]} · {items.length}
              </p>
              {items.map((c) => (
                <ConversationRow
                  key={c.conversation_id}
                  conversation={c}
                  selected={c.conversation_id === selectedId}
                  onSelect={() => onSelect(c.conversation_id)}
                />
              ))}
            </div>
          )
        })
      )}
    </div>
  )
}
