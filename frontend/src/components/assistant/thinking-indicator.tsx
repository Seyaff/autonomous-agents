"use client"

import * as React from "react"
import { SparklesIcon } from "lucide-react"

import { randomThinkingWord, toolStep } from "@/lib/agent-words"
import type { AgentStep } from "@/components/assistant/assistant-provider"

/** What the agent is doing right now: the running tool's step, or a rotating thinking word, with a shimmer. */
export function ThinkingIndicator({ steps }: { steps: AgentStep[] }) {
  const running = [...steps].reverse().find((s) => !s.done)
  const [word, setWord] = React.useState(() => randomThinkingWord())
  const [seconds, setSeconds] = React.useState(0)

  React.useEffect(() => {
    const wordTimer = window.setInterval(() => setWord((w) => randomThinkingWord(w)), 2400)
    const clock = window.setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => {
      window.clearInterval(wordTimer)
      window.clearInterval(clock)
    }
  }, [])

  const label = running ? toolStep(running.name, false) : word

  return (
    <div className="flex items-center gap-2 text-[13px]" role="status" aria-live="polite">
      <SparklesIcon className="size-3.5 shrink-0 animate-pulse text-ai" />
      <span
        key={label}
        className="agent-shimmer font-medium"
        style={{ animation: "agent-word-in 220ms ease-out, agent-shimmer 1.8s linear infinite" }}
      >
        {label}…
      </span>
      {seconds >= 3 && <span className="font-mono text-[11px] text-muted-foreground tabular-nums">{seconds}s</span>}
    </div>
  )
}
