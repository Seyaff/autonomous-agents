"use client"

import * as React from "react"
import { notFound } from "next/navigation"
import { ArrowLeftIcon, MoreVerticalIcon, SendIcon } from "lucide-react"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import { MESSAGE_STATUS_CONFIG } from "@/lib/status"
import { useConversation } from "@/hooks/inbox/use-conversation"
import { useSendMessage } from "@/hooks/inbox/use-send-message"
import { useMarkConversationRead } from "@/hooks/inbox/use-mark-read"

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

export default function InboxConversationPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = React.use(params)
  const { data, isLoading, isError } = useConversation(id)
  const { mutate: send, isPending: isSending } = useSendMessage(id)
  const { mutate: markRead } = useMarkConversationRead()

  const [draft, setDraft] = React.useState("")
  const scrollRef = React.useRef<HTMLDivElement>(null)

  const conversation = data?.conversation
  const messages = React.useMemo(() => data?.messages ?? [], [data])

  React.useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    })
  }, [messages])

  React.useEffect(() => {
    if (conversation && conversation.unread_count > 0) {
      markRead(id)
    }
    // Only re-run when the conversation identity or its unread count changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, conversation?.unread_count])

  if (isError) notFound()

  function handleSend(e: React.FormEvent) {
    e.preventDefault()
    const text = draft.trim()
    if (!text || isSending) return
    send(text)
    setDraft("")
  }

  return (
    <div className="flex h-full flex-1 flex-col">
      {/* Header */}
      <header className="flex shrink-0 items-center gap-3 border-b bg-background px-4 py-3">
        <Button variant="ghost" size="icon" className="md:hidden">
          <ArrowLeftIcon className="size-4" />
          <span className="sr-only">Back</span>
        </Button>

        {isLoading ? (
          <>
            <Skeleton className="size-9 rounded-full" />
            <Skeleton className="h-4 w-32" />
          </>
        ) : (
          <>
            <Avatar className="size-9">
              <AvatarFallback>
                {initials(conversation?.customer_name || conversation?.customer_phone || "?")}
              </AvatarFallback>
            </Avatar>

            <div className="flex min-w-0 flex-1 flex-col">
              <span className="truncate text-sm font-medium">
                {conversation?.customer_name || "Unknown customer"}
              </span>
              <span className="truncate text-xs text-muted-foreground">
                {conversation?.customer_phone}
              </span>
            </div>
          </>
        )}

        <div className="flex items-center gap-1">
          <DropdownMenu>
            <DropdownMenuTrigger className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground">
              <MoreVerticalIcon className="size-4" />
              <span className="sr-only">More</span>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-40">
              <DropdownMenuItem>Archive</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive">
                Close conversation
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex flex-1 flex-col gap-4 overflow-y-auto bg-muted/30 p-6"
      >
        {isLoading ? (
          <div className="space-y-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton
                key={i}
                className={cn(
                  "h-10 w-2/3 rounded-2xl",
                  i % 2 === 0 ? "ml-auto" : ""
                )}
              />
            ))}
          </div>
        ) : messages.length === 0 ? (
          <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
            No messages in this conversation yet.
          </div>
        ) : (
          messages.map((message) => {
            const isOutbound =
              message.sender === "agent" || message.sender === "human"
            return (
              <div
                key={message.message_id}
                className={cn(
                  "flex w-full items-end gap-2",
                  isOutbound ? "justify-end" : "justify-start"
                )}
              >
                {!isOutbound && (
                  <Avatar className="size-7 shrink-0">
                    <AvatarFallback className="text-[10px]">
                      {initials(
                        conversation?.customer_name ||
                          conversation?.customer_phone ||
                          "?"
                      )}
                    </AvatarFallback>
                  </Avatar>
                )}

                <div
                  className={cn(
                    "flex max-w-[75%] flex-col gap-1 rounded-2xl px-3.5 py-2 text-sm shadow-sm",
                    isOutbound
                      ? "rounded-br-sm bg-primary text-primary-foreground"
                      : "rounded-bl-sm bg-background"
                  )}
                >
                  <p className="whitespace-pre-wrap leading-snug">
                    {message.content}
                  </p>
                  <div className="flex items-center gap-1.5">
                    <span
                      className={cn(
                        "text-[10px] tabular-nums",
                        isOutbound
                          ? "text-primary-foreground/70"
                          : "text-muted-foreground"
                      )}
                    >
                      {new Date(message.created_at).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                    {isOutbound && (
                      <span
                        className={cn(
                          "text-[10px]",
                          isOutbound
                            ? "text-primary-foreground/70"
                            : "text-muted-foreground"
                        )}
                      >
                        · {MESSAGE_STATUS_CONFIG[message.status]?.label ?? message.status}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Composer */}
      <form
        onSubmit={handleSend}
        className="flex shrink-0 items-center gap-2 border-t bg-background p-3"
      >
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Type a message..."
          disabled={isSending || isLoading}
          className="flex-1"
        />
        <Button
          type="submit"
          size="icon"
          className="size-9 shrink-0"
          disabled={!draft.trim() || isSending}
        >
          <SendIcon className="size-4" />
          <span className="sr-only">Send</span>
        </Button>
      </form>
    </div>
  )
}
