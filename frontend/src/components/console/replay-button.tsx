"use client"

import { SparklesIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useLunchRushReplay } from "@/hooks/console/use-lunch-rush-replay"

export function ReplayLunchRushButton({
  onSelectConversation,
}: {
  onSelectConversation: (id: string) => void
}) {
  const { play, isPlaying } = useLunchRushReplay(onSelectConversation)

  return (
    <Button variant="outline" size="sm" className="gap-1.5" onClick={play} disabled={isPlaying}>
      <SparklesIcon className="size-3.5" />
      {isPlaying ? "Playing…" : "Replay lunch rush"}
    </Button>
  )
}
