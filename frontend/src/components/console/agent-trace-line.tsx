import { cn } from "@/lib/utils"
import type { AgentTraceStep } from "@/lib/mock/messages"

export function AgentTraceLine({ step }: { step: AgentTraceStep }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[75%] text-right font-mono text-[12px] text-muted-foreground">
        <span className="text-ai">↳</span> {step.tool}({step.args}) →{" "}
        <span className={cn(step.resultTone === "ok" ? "text-ok" : "text-need")}>{step.result}</span>{" "}
        · {step.durationS.toFixed(2)}s
      </p>
    </div>
  )
}
