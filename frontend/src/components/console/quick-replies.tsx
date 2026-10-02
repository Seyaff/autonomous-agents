import { Button } from "@/components/ui/button"

const QUICK_REPLIES = ["Offer refund", "Offer compensation", "Schedule call back"]

export function QuickReplies({ onPick }: { onPick: (text: string) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5 border-t border-border bg-card px-3 pt-2">
      {QUICK_REPLIES.map((text) => (
        <Button
          key={text}
          type="button"
          variant="outline"
          size="xs"
          className="rounded-full"
          onClick={() => onPick(text)}
        >
          {text}
        </Button>
      ))}
    </div>
  )
}
