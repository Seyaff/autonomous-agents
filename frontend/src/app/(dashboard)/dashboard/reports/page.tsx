"use client"

import * as React from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { LiveOnly } from "@/components/dashboard/live-only"
import { useWeeklyReports } from "@/hooks/reports/use-weekly-reports"
import { useCurrentTenant } from "@/hooks/tenant/use-current-tenant"
import { USE_MOCKS } from "@/lib/mocks"
import type { WeeklyReport } from "@/services/reports/reports.service"

function money(value: number, currency: string) {
  return `${currency} ${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" })
}

export default function ReportsPage() {
  if (USE_MOCKS) return <LiveOnly title="Reports" />
  return <Reports />
}

function Reports() {
  const { list, generate } = useWeeklyReports()
  const { data: tenant } = useCurrentTenant()
  const currency = tenant?.currency ?? "USD"
  const reports = list.data ?? []
  const [selectedId, setSelectedId] = React.useState<string | null>(null)
  const [confirming, setConfirming] = React.useState(false)

  const selected: WeeklyReport | undefined =
    reports.find((r) => r._id === selectedId) ?? reports[0]

  function runGenerate() {
    if (!confirming) {
      setConfirming(true)
      return
    }
    generate.mutate(undefined, {
      onSuccess: (report) => {
        setSelectedId(report._id ?? null)
        toast(report.delivered_via_whatsapp ? "Report created and sent to your WhatsApp." : "Report created.")
      },
      onError: () => toast.error("Could not create the report."),
      onSettled: () => setConfirming(false),
    })
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-border bg-card px-4 py-2">
        <div>
          <h1 className="text-sm font-medium">Reports</h1>
          <p className="font-mono text-[11px] text-muted-foreground">Weekly summaries of orders, revenue and customers</p>
        </div>
        <div className="flex items-center gap-2">
          {confirming && (
            <span className="font-mono text-[11px] text-muted-foreground">This also sends the report to your WhatsApp.</span>
          )}
          <Button size="sm" variant={confirming ? "destructive" : "outline"} onClick={runGenerate} disabled={generate.isPending}>
            {generate.isPending ? "Creating..." : confirming ? "Yes, create and send" : "Create report"}
          </Button>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 gap-4 overflow-hidden p-4 lg:grid-cols-[260px_1fr]">
        <aside className="min-h-0 overflow-y-auto rounded-lg border border-border bg-card">
          {list.isLoading ? (
            <p className="p-4 font-mono text-[12px] text-muted-foreground">Loading...</p>
          ) : reports.length === 0 ? (
            <p className="p-4 font-mono text-[12px] text-muted-foreground">No reports yet.</p>
          ) : (
            <ul>
              {reports.map((r) => (
                <li key={r._id ?? r.created_at}>
                  <button
                    onClick={() => setSelectedId(r._id ?? null)}
                    className={`w-full border-b border-border px-4 py-3 text-left hover:bg-muted ${
                      selected?._id === r._id ? "bg-muted" : ""
                    }`}
                  >
                    <p className="text-sm">
                      {fmtDate(r.metrics.period_start)} – {fmtDate(r.metrics.period_end)}
                    </p>
                    <p className="font-mono text-[11px] text-muted-foreground">
                      {r.metrics.total_orders} orders · {money(r.metrics.total_revenue, currency)}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <section className="min-h-0 overflow-y-auto rounded-lg border border-border bg-card p-4">
          {!selected ? (
            <p className="font-mono text-[12px] text-muted-foreground">Pick a report, or create one for the last 7 days.</p>
          ) : (
            <div className="space-y-5">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Stat label="Orders" value={selected.metrics.total_orders.toString()} />
                <Stat label="Revenue" value={money(selected.metrics.total_revenue, currency)} />
                <Stat
                  label="Revenue vs prior week"
                  value={`${selected.metrics.revenue_growth_pct >= 0 ? "+" : ""}${selected.metrics.revenue_growth_pct}%`}
                />
                <Stat label="Avg order" value={money(selected.metrics.average_order_value, currency)} />
                <Stat label="Delivered" value={selected.metrics.delivered_orders.toString()} />
                <Stat label="Cancelled" value={`${selected.metrics.cancellation_rate}%`} />
                <Stat label="Customers" value={selected.metrics.unique_customers.toString()} />
                <Stat label="Chats" value={selected.metrics.total_conversations.toString()} />
              </div>

              {selected.metrics.top_items.length > 0 && (
                <div>
                  <h2 className="text-sm font-medium">Top items</h2>
                  <ul className="mt-2 divide-y divide-border">
                    {(selected.metrics.top_items as { name: string; quantity?: number; count?: number }[]).map((item, i) => (
                      <li key={`${item.name}-${i}`} className="flex justify-between py-1.5 text-sm">
                        <span>{item.name}</span>
                        <span className="font-mono text-[12px] text-muted-foreground">
                          {item.quantity ?? item.count ?? 0}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div>
                <h2 className="text-sm font-medium">Summary</h2>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">{selected.summary}</p>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border p-3">
      <p className="font-mono text-[11px] text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-medium">{value}</p>
    </div>
  )
}
