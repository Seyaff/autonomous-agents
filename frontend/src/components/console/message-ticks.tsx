import type { Message } from "@/services/inbox/inbox.service"

export function MessageTicks({ status }: { status: Message["status"] }) {
  if (status === "failed") {
    return (
      <button type="button" className="rounded-[5px] bg-need-soft px-1.5 py-0.5 font-mono text-[10px] text-need">
        Not sent · Retry
      </button>
    )
  }
  if (status === "read") {
    return <span className="font-mono text-[10px] text-new">✓✓</span>
  }
  if (status === "delivered") {
    return <span className="font-mono text-[10px] text-muted-foreground">✓✓</span>
  }
  if (status === "sent") {
    return <span className="font-mono text-[10px] text-muted-foreground">✓</span>
  }
  return null
}
