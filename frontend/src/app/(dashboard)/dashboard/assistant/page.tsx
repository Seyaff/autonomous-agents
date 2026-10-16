"use client"

import { SparklesIcon } from "lucide-react"

import { AssistantChat } from "@/components/assistant/assistant-chat"
import { ShortcutHint } from "@/components/assistant/assistant-panel"

export default function AssistantPage() {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 items-center gap-2 border-b border-border bg-card px-4 py-2">
        <SparklesIcon className="size-4 text-ai" />
        <div className="min-w-0 flex-1">
          <h1 className="text-sm font-medium">Agent</h1>
          <p className="font-mono text-[11px] text-muted-foreground">
            Ask about sales, orders and chats, or say what to change. Open it from any page too.
          </p>
        </div>
        <ShortcutHint />
      </div>
      <div className="mx-auto flex min-h-0 w-full max-w-3xl flex-1 flex-col">
        <AssistantChat autoFocus />
      </div>
    </div>
  )
}
