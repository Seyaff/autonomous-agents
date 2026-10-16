"use client"

import * as React from "react"
import { SparklesIcon, SquarePenIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { AssistantChat } from "@/components/assistant/assistant-chat"
import { useAssistant } from "@/components/assistant/assistant-provider"

export function ShortcutHint({ className }: { className?: string }) {
  // The platform never changes, so there's nothing to subscribe to; the server render assumes "Ctrl".
  const mac = React.useSyncExternalStore(
    () => () => {},
    () => /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent),
    () => false,
  )
  return (
    <kbd className={"rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground " + (className ?? "")}>
      {mac ? "⌘" : "Ctrl"} K
    </kbd>
  )
}

/** The agent, slid in from the right on any dashboard page. */
export function AssistantPanel() {
  const { open, setOpen, clear, sending, messages } = useAssistant()

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetContent side="right" className="w-full gap-0 p-0 sm:max-w-md">
        <SheetHeader className="flex-row items-center gap-2 border-b border-border px-4 py-3">
          <SparklesIcon className="size-4 text-ai" />
          <div className="min-w-0 flex-1">
            <SheetTitle className="text-sm">Agent</SheetTitle>
            <SheetDescription className="text-[11px]">Runs your business from one text box.</SheetDescription>
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            className="mr-8"
            onClick={() => void clear()}
            disabled={sending || messages.length === 0}
            aria-label="New conversation"
            title="New conversation"
          >
            <SquarePenIcon className="size-4" />
          </Button>
        </SheetHeader>
        <AssistantChat autoFocus={open} />
      </SheetContent>
    </Sheet>
  )
}

/** The button in the top bar that opens the agent. */
export function AssistantLauncher() {
  const { ask, sending } = useAssistant()
  return (
    <button
      type="button"
      onClick={() => ask()}
      className="flex items-center gap-2 rounded-md border border-border bg-background px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-ai/50 hover:text-foreground"
    >
      <SparklesIcon className={"size-3.5 text-ai " + (sending ? "animate-pulse" : "")} />
      <span className="hidden sm:inline">{sending ? "Agent is working…" : "Ask agent"}</span>
      <ShortcutHint className="hidden md:inline" />
    </button>
  )
}
