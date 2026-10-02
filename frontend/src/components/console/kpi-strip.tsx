"use client"

import { useEffect, useRef, useState } from "react"
import { cn } from "@/lib/utils"
import { formatMoney } from "@/lib/currency"
import type { KpiValue } from "@/lib/mock/kpis"

function formatValue(kpi: KpiValue, currency: string) {
  if (kpi.format === "currency") return formatMoney(kpi.value, currency)
  if (kpi.format === "percent") return `${kpi.value}%`
  return kpi.value.toLocaleString()
}

function KpiItem({ kpi, currency }: { kpi: KpiValue; currency: string }) {
  const [flash, setFlash] = useState(false)
  const prev = useRef(kpi.value)

  useEffect(() => {
    if (kpi.value > prev.current) {
      setFlash(true)
      const t = setTimeout(() => setFlash(false), 900)
      prev.current = kpi.value
      return () => clearTimeout(t)
    }
    prev.current = kpi.value
  }, [kpi.value])

  return (
    <div className="flex items-baseline gap-1.5">
      <span className="font-mono text-[11px] tracking-[.08em] text-muted-foreground uppercase">
        {kpi.label}
      </span>
      <span className={cn("font-mono text-sm font-medium tabular-nums transition-colors", flash && "text-ok")}>
        {formatValue(kpi, currency)}
      </span>
    </div>
  )
}

export function KpiStrip({ kpis, currency }: { kpis: KpiValue[]; currency: string }) {
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-1">
      {kpis.map((kpi) => (
        <KpiItem key={kpi.key} kpi={kpi} currency={currency} />
      ))}
    </div>
  )
}
