"use client"

// TODO(backend): no billing/usage endpoint exists yet — mock data only.
// Per DESIGN.md §7, hide this meter entirely once real billing ships.
const MOCK_USED = 1284
const MOCK_LIMIT = 2000

export function PlanUsageMeter() {
  const pct = Math.min(100, Math.round((MOCK_USED / MOCK_LIMIT) * 100))

  return (
    <div className="hidden items-center gap-2 md:flex">
      <span className="font-mono text-xs text-muted-foreground">
        Growth plan · {MOCK_USED.toLocaleString()} / {MOCK_LIMIT.toLocaleString()} AI conversations
      </span>
      <div className="h-[5px] w-24 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
