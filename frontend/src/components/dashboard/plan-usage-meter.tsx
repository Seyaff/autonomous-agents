"use client"

import { useUsage } from "@/hooks/billing/use-usage"
import { USE_MOCKS } from "@/lib/mocks"

/** AI conversations used this month against the plan. Hidden when there is
 * nothing real to show (mock mode, loading, or the usage call failed). */
export function PlanUsageMeter() {
  const { data } = useUsage()
  if (USE_MOCKS || !data) return null

  const pct = Math.min(100, Math.round((data.used / data.limit) * 100))

  return (
    <div className="hidden items-center gap-2 md:flex">
      <span className="font-mono text-xs text-muted-foreground">
        {data.plan_name} · {data.used.toLocaleString()} / {data.limit.toLocaleString()} AI conversations
      </span>
      <div className="h-[5px] w-24 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
