import { cn } from "@/lib/utils"

export type ChipTone = "ai" | "need" | "ok" | "new" | "neutral"

const toneClass: Record<ChipTone, string> = {
  ai: "bg-ai-soft text-ai",
  need: "bg-need-soft text-need",
  ok: "bg-ok-soft text-ok",
  new: "bg-new-soft text-new",
  neutral: "bg-muted text-muted-foreground",
}

const dotClass: Record<ChipTone, string> = {
  ai: "bg-ai",
  need: "bg-need",
  ok: "bg-ok",
  new: "bg-new",
  neutral: "bg-muted-foreground",
}

export function StatusChip({
  tone,
  label,
  className,
}: {
  tone: ChipTone
  label: string
  className?: string
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-[5px] px-1.5 py-0.5 font-mono text-[11px] tracking-wide",
        toneClass[tone],
        className
      )}
    >
      <span className={cn("size-1.5 rounded-full", dotClass[tone])} />
      {label}
    </span>
  )
}
