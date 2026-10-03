"use client"

import * as React from "react"
import { useRouter, usePathname } from "next/navigation"
import { SearchIcon } from "lucide-react"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Skeleton } from "@/components/ui/skeleton"
import { ConversationRow } from "@/components/console/conversation-row"
import { useQueue, type QueueGroups } from "@/hooks/console/use-queue"

const GROUP_ORDER: (keyof QueueGroups)[] = ["needs_you", "owner_handling", "agent_handling", "resolved"]
const GROUP_LABELS: Record<keyof QueueGroups, string> = {
  needs_you: "Needs you",
  owner_handling: "You're handling",
  agent_handling: "Agent handling",
  resolved: "Resolved today",
}

const INBOX_PREFIX = "/dashboard/inbox/"

export function InboxSidebar() {
  const router = useRouter()
  const pathname = usePathname()
  const [search, setSearch] = React.useState("")
  const [unreadOnly, setUnreadOnly] = React.useState(false)

  const { groups, isLoading } = useQueue(search || undefined)

  const filtered: QueueGroups = {
    needs_you: groups.needs_you.filter((c) => !unreadOnly || c.unread_count > 0),
    owner_handling: groups.owner_handling.filter((c) => !unreadOnly || c.unread_count > 0),
    agent_handling: groups.agent_handling.filter((c) => !unreadOnly || c.unread_count > 0),
    resolved: groups.resolved.filter((c) => !unreadOnly || c.unread_count > 0),
  }
  const total = GROUP_ORDER.reduce((n, key) => n + filtered[key].length, 0)

  // decodeURIComponent is safe to apply even if usePathname() already
  // decoded it — it's a no-op once there's no %XX left to unescape.
  const selectedId = pathname.startsWith(INBOX_PREFIX)
    ? decodeURIComponent(pathname.slice(INBOX_PREFIX.length))
    : null

  return (
    <div className="flex h-full w-full shrink-0 flex-col border-r border-border bg-sidebar md:w-[320px]">
      <div className="flex shrink-0 flex-col gap-3 border-b border-border p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-medium">Inbox</h2>
          <Label className="flex items-center gap-2 text-sm">
            <span>Unread</span>
            <Switch checked={unreadOnly} onCheckedChange={setUnreadOnly} className="shadow-none" />
          </Label>
        </div>
        <div className="relative">
          <SearchIcon className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by name or phone..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="space-y-3 p-3">
            {Array.from({ length: 6 }).map((_, i) => (
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
            const items = filtered[key]
            if (items.length === 0) return null
            return (
              <div key={key}>
                <p className="sticky top-0 z-10 bg-sidebar px-3 pt-3 pb-1 font-mono text-[11px] tracking-[.08em] text-muted-foreground uppercase">
                  {GROUP_LABELS[key]} · {items.length}
                </p>
                {items.map((c) => (
                  <ConversationRow
                    key={c.conversation_id}
                    conversation={c}
                    selected={c.conversation_id === selectedId}
                    onSelect={() =>
                      router.push(`/dashboard/inbox/${encodeURIComponent(c.conversation_id)}`)
                    }
                  />
                ))}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
