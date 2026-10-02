"use client"

import * as React from "react"
import { notFound } from "next/navigation"
import {
  ArrowLeftIcon,
  InfoIcon,
  MoreVerticalIcon,
  PaperclipIcon,
  SearchIcon,
  SendIcon,
  SmileIcon,
} from "lucide-react"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"
import { mails } from "@/components/inbox/inbox-sidebar"

type Message = {
  id: number
  from: "me" | "them"
  text: string
  time: string
}

const baseMessages: Message[] = [
  { id: 1, from: "them", text: "Hey! Just wanted to follow up on the meeting notes.", time: "09:12 AM" },
  { id: 2, from: "me", text: "Sure thing, I'll send them over in a bit.", time: "09:14 AM" },
  { id: 3, from: "them", text: "Perfect. Also, can we push the design review to 3 PM?", time: "09:15 AM" },
  { id: 4, from: "me", text: "3 PM works. I'll update the calendar invite.", time: "09:16 AM" },
  { id: 5, from: "them", text: "Thanks! See you then 👋", time: "09:17 AM" },
  { id: 6, from: "me", text: "See you!", time: "09:17 AM" },
]

export default function InboxConversationPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  // Next.js 15: params is a promise
  const { id } = React.use(params)
  const conversation = mails.find((m) => m.id === id)

  if (!conversation) notFound()

  const [messages, setMessages] = React.useState<Message[]>(baseMessages)
  const [draft, setDraft] = React.useState("")
  const scrollRef = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    })
  }, [messages])

  function handleSend(e: React.FormEvent) {
    e.preventDefault()
    const text = draft.trim()
    if (!text) return

    setMessages((prev) => [
      ...prev,
      {
        id: prev.length + 1,
        from: "me",
        text,
        time: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      },
    ])
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

        <Avatar className="size-9">
          <AvatarImage src="" alt={conversation.name} />
          <AvatarFallback>
            {conversation.name
              .split(" ")
              .map((n) => n[0])
              .join("")}
          </AvatarFallback>
        </Avatar>

        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-medium">
              {conversation.name}
            </span>
            <Badge
              variant="secondary"
              className="h-4 gap-1 px-1.5 text-[10px] font-normal"
            >
              <span className="size-1.5 rounded-full bg-emerald-500" />
              Online
            </Badge>
          </div>
          <span className="truncate text-xs text-muted-foreground">
            {conversation.email}
          </span>
        </div>

        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" className="size-8">
            <SearchIcon className="size-4" />
            <span className="sr-only">Search</span>
          </Button>
          <Button variant="ghost" size="icon" className="size-8">
            <InfoIcon className="size-4" />
            <span className="sr-only">Details</span>
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground">
              <MoreVerticalIcon className="size-4" />
              <span className="sr-only">More</span>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-40">
              <DropdownMenuItem>Mark as unread</DropdownMenuItem>
              <DropdownMenuItem>Star conversation</DropdownMenuItem>
              <DropdownMenuItem>Mute</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive">Delete</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex flex-1 flex-col gap-4 overflow-y-auto bg-muted/30 p-6"
      >
        <div className="flex items-center gap-3 py-2">
          <Separator className="flex-1" />
          <span className="text-xs font-medium text-muted-foreground">
            Today
          </span>
          <Separator className="flex-1" />
        </div>

        {messages.map((message) => {
          const isMe = message.from === "me"
          return (
            <div
              key={message.id}
              className={cn(
                "flex w-full items-end gap-2",
                isMe ? "justify-end" : "justify-start"
              )}
            >
              {!isMe && (
                <Avatar className="size-7 shrink-0">
                  <AvatarFallback className="text-[10px]">
                    {conversation.name
                      .split(" ")
                      .map((n) => n[0])
                      .join("")}
                  </AvatarFallback>
                </Avatar>
              )}

              <div
                className={cn(
                  "flex max-w-[75%] flex-col gap-1 rounded-2xl px-3.5 py-2 text-sm shadow-sm",
                  isMe
                    ? "rounded-br-sm bg-primary text-primary-foreground"
                    : "rounded-bl-sm bg-background"
                )}
              >
                <p className="whitespace-pre-wrap leading-snug">
                  {message.text}
                </p>
                <span
                  className={cn(
                    "text-[10px] tabular-nums",
                    isMe
                      ? "text-primary-foreground/70"
                      : "text-muted-foreground"
                  )}
                >
                  {message.time}
                </span>
              </div>
            </div>
          )
        })}
      </div>

      {/* Composer */}
      <form
        onSubmit={handleSend}
        className="flex shrink-0 items-center gap-2 border-t bg-background p-3"
      >
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-8 shrink-0"
        >
          <PaperclipIcon className="size-4" />
          <span className="sr-only">Attach</span>
        </Button>

        <div className="relative flex-1">
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Type a message..."
            className="pr-9"
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="absolute top-1/2 right-1 size-7 -translate-y-1/2"
          >
            <SmileIcon className="size-4" />
            <span className="sr-only">Emoji</span>
          </Button>
        </div>

        <Button type="submit" size="icon" className="size-9 shrink-0">
          <SendIcon className="size-4" />
          <span className="sr-only">Send</span>
        </Button>
      </form>
    </div>
  )
}