"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { SearchIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { cn } from "@/lib/utils"
import { useConversations } from "@/hooks/inbox/use-conversations"

function relativeTime(iso: string) {
  const diffMs = Date.now() - new Date(iso).getTime()
  const minutes = Math.round(diffMs / 60000)
  if (minutes < 1) return "now"
  if (minutes < 60) return `${minutes}m`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h`
  return `${Math.round(hours / 24)}d`
}

export function InboxSidebar() {
  const pathname = usePathname()
  const [search, setSearch] = React.useState("")
  const [unreadOnly, setUnreadOnly] = React.useState(false)

  const { data, isLoading } = useConversations({
    search: search || undefined,
    limit: 50,
  })

  const conversations = (data?.conversations ?? []).filter(
    (c) => !unreadOnly || c.unread_count > 0
  )

  return (
    <div className="flex h-full w-[360px] shrink-0 flex-col border-r bg-sidebar">
      <div className="flex shrink-0 flex-col gap-3 border-b p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-medium">Inbox</h2>
          <Label className="flex items-center gap-2 text-sm">
            <span>Unread</span>
            <Switch
              checked={unreadOnly}
              onCheckedChange={setUnreadOnly}
              className="shadow-none"
            />
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

      <div className="flex-1 overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {isLoading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="space-y-2 border-b p-4">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-3 w-full" />
            </div>
          ))
        ) : conversations.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-1 p-8 text-center">
            <p className="text-sm font-medium">No conversations yet</p>
            <p className="text-xs text-muted-foreground">
              Messages from your customers on WhatsApp will show up here.
            </p>
          </div>
        ) : (
          conversations.map((conv) => {
            const href = `/dashboard/inbox/${conv.conversation_id}`
            const isActive = pathname === href
            return (
              <Link
                key={conv.conversation_id}
                href={href}
                className={cn(
                  "flex flex-col items-start gap-1.5 border-b p-4 text-sm leading-tight last:border-b-0 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                  isActive && "bg-sidebar-accent text-sidebar-accent-foreground"
                )}
              >
                <div className="flex w-full items-center gap-2">
                  <span className="truncate font-medium">
                    {conv.customer_name || conv.customer_phone}
                  </span>
                  <span className="ml-auto shrink-0 text-xs text-muted-foreground">
                    {relativeTime(conv.last_activity_at)}
                  </span>
                </div>
                <div className="flex w-full items-center gap-2">
                  <span className="line-clamp-1 flex-1 text-xs text-muted-foreground">
                    {conv.last_message?.content ?? "No messages yet"}
                  </span>
                  {conv.unread_count > 0 && (
                    <Badge className="h-5 min-w-5 shrink-0 justify-center rounded-full px-1.5 text-[10px]">
                      {conv.unread_count}
                    </Badge>
                  )}
                </div>
              </Link>
            )
          })
        )}
      </div>
    </div>
  )
}
