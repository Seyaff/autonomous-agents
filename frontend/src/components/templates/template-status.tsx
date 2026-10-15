import { cn } from "@/lib/utils"
import type { TemplateStatus } from "@/services/templates/templates.service"

const LOOK: Record<string, { label: string; className: string }> = {
  APPROVED: { label: "Approved", className: "bg-ok-soft text-ok" },
  PENDING: { label: "In review", className: "bg-ai-soft text-ai" },
  IN_APPEAL: { label: "In appeal", className: "bg-ai-soft text-ai" },
  REJECTED: { label: "Rejected", className: "bg-need-soft text-need" },
  PAUSED: { label: "Paused by Meta", className: "bg-need-soft text-need" },
  DISABLED: { label: "Disabled by Meta", className: "bg-need-soft text-need" },
}

export function TemplateStatusBadge({ status }: { status: TemplateStatus }) {
  const look = LOOK[status] ?? { label: status.toLowerCase(), className: "bg-muted text-muted-foreground" }
  return (
    <span className={cn("rounded-[5px] px-1.5 py-0.5 font-mono text-[10px]", look.className)}>{look.label}</span>
  )
}
