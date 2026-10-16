"use client"

import * as React from "react"
import { ArrowUpIcon, SparklesIcon } from "lucide-react"

import { useAssistant } from "@/components/assistant/assistant-provider"
import { ShortcutHint } from "@/components/assistant/assistant-panel"

// Cycled in the empty bar, so owners see the range of what they can type.
const PROMPTS = [
  "How did we do today?",
  "Which chats need me?",
  "What sold best this week?",
  "Who are my top 5 customers?",
  "Accept all pending orders",
  "Close on Sundays",
  "Send our offer template to everyone who ordered this month",
]

/** The agent's text box on the front page. Typing here opens the panel with the reply. */
export function AskBar() {
  const { ask, sending } = useAssistant()
  const [text, setText] = React.useState("")
  const [hint, setHint] = React.useState(0)

  React.useEffect(() => {
    const timer = window.setInterval(() => setHint((h) => (h + 1) % PROMPTS.length), 3500)
    return () => window.clearInterval(timer)
  }, [])

  const submit = () => {
    if (!text.trim() || sending) {
      ask()
      return
    }
    ask(text)
    setText("")
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
      className="group flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-border bg-background px-3 py-1.5 transition-colors focus-within:border-ai/60 focus-within:ring-2 focus-within:ring-ai/15 md:max-w-xl"
    >
      <SparklesIcon className={"size-4 shrink-0 text-ai " + (sending ? "animate-pulse" : "")} />
      <div className="relative min-w-0 flex-1">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          aria-label="Ask your agent"
          className="w-full bg-transparent text-sm outline-none"
          maxLength={2000}
        />
        {!text && (
          <span
            key={hint}
            className="pointer-events-none absolute inset-0 truncate text-sm text-muted-foreground"
            style={{ animation: "agent-word-in 300ms ease-out" }}
          >
            {sending ? "Your agent is working…" : `Ask your agent: "${PROMPTS[hint]}"`}
          </span>
        )}
      </div>
      {text.trim() ? (
        <button type="submit" className="rounded-md bg-primary p-1 text-primary-foreground" aria-label="Send">
          <ArrowUpIcon className="size-3.5" />
        </button>
      ) : (
        <ShortcutHint className="hidden shrink-0 sm:inline" />
      )}
    </form>
  )
}
