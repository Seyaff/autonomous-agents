"use client"

import { useQuery } from "@tanstack/react-query"

import { getOperatedAlerts, getRestaurants, type OperatedRestaurant, type RestaurantHealth } from "@/services/operations/operations.service"

const HEALTH: Record<RestaurantHealth, { label: string; cls: string }> = {
  healthy: { label: "Healthy", cls: "bg-ok-soft text-ok" },
  needs_attention: { label: "Needs attention", cls: "bg-need-soft text-need" },
  setting_up: { label: "Setting up", cls: "bg-muted text-muted-foreground" },
}

const SEVERITY_DOT: Record<string, string> = {
  critical: "bg-need",
  warning: "bg-ai",
  info: "bg-new",
}

function ago(iso: string | null) {
  if (!iso) return "never"
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins} min ago`
  if (mins < 1440) return `${Math.round(mins / 60)} h ago`
  return `${Math.round(mins / 1440)} d ago`
}

/** What is happening across every restaurant, at a glance. Read-only. */
export default function OperationsPage() {
  const restaurants = useQuery({ queryKey: ["ops", "restaurants"], queryFn: getRestaurants, refetchInterval: 30_000 })
  const alerts = useQuery({ queryKey: ["ops", "alerts"], queryFn: getOperatedAlerts, refetchInterval: 30_000 })

  const rows = restaurants.data?.restaurants ?? []
  const counts = {
    total: rows.length,
    attention: rows.filter((r) => r.health === "needs_attention").length,
    setting_up: rows.filter((r) => r.health === "setting_up").length,
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-lg">Operations</h1>
          <p className="font-mono text-[12px] text-muted-foreground">
            {counts.total} restaurants · {counts.attention} need attention · {counts.setting_up} setting up
          </p>
        </div>
        <p className="font-mono text-[11px] text-muted-foreground">Refreshes every 30 seconds</p>
      </div>

      <section className="overflow-x-auto rounded-lg border border-border bg-card">
        <table className="w-full min-w-[960px] text-sm">
          <thead className="bg-muted/50 text-left font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
            <tr>
              <th className="px-3 py-2 font-medium">Restaurant</th>
              <th className="px-3 py-2 font-medium">Health</th>
              <th className="px-3 py-2 font-medium">WhatsApp</th>
              <th className="px-3 py-2 font-medium">Last customer</th>
              <th className="px-3 py-2 text-right font-medium">Msgs today</th>
              <th className="px-3 py-2 text-right font-medium">Orders today</th>
              <th className="px-3 py-2 text-right font-medium">Failed 24h</th>
              <th className="px-3 py-2 text-right font-medium">Open escalations</th>
              <th className="px-3 py-2 text-right font-medium">AI this month</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <Row key={r.tenant_id} r={r} />
            ))}
            {restaurants.isSuccess && rows.length === 0 && (
              <tr>
                <td colSpan={9} className="px-3 py-6 text-center font-mono text-[12px] text-muted-foreground">
                  No restaurants yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      <section className="rounded-lg border border-border bg-card">
        <div className="border-b border-border px-4 py-2 font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
          Latest alerts, all restaurants
        </div>
        <ul className="divide-y divide-border">
          {(alerts.data?.alerts ?? []).map((a) => (
            <li key={a.id} className={`flex gap-3 px-4 py-2.5 ${a.read ? "opacity-60" : ""}`}>
              <span className={`mt-1.5 size-2 shrink-0 rounded-full ${SEVERITY_DOT[a.severity] ?? "bg-new"}`} aria-hidden />
              <div className="min-w-0">
                <p className="text-sm">
                  <span className="font-medium">{a.business_name}</span> · {a.title}
                </p>
                {a.detail && <p className="text-xs text-muted-foreground">{a.detail}</p>}
                <p className="font-mono text-[11px] text-muted-foreground">{ago(a.created_at)}</p>
              </div>
            </li>
          ))}
          {alerts.isSuccess && (alerts.data?.alerts ?? []).length === 0 && (
            <li className="px-4 py-6 font-mono text-[12px] text-muted-foreground">No alerts.</li>
          )}
        </ul>
      </section>
    </div>
  )
}

function Row({ r }: { r: OperatedRestaurant }) {
  const health = HEALTH[r.health]
  return (
    <tr className="border-t border-border align-top">
      <td className="px-3 py-2.5">
        <p className="font-medium">{r.business_name}</p>
        <p className="font-mono text-[11px] text-muted-foreground">
          {r.owner_email ?? "no owner"}{r.country ? ` · ${r.country}` : ""}
        </p>
      </td>
      <td className="px-3 py-2.5">
        <span className={`inline-flex rounded-md px-2 py-0.5 font-mono text-[11px] ${health.cls}`}>{health.label}</span>
      </td>
      <td className="px-3 py-2.5">
        <p className={r.whatsapp_status === "connected" ? "text-ok" : r.whatsapp_status === "error" ? "text-need" : "text-muted-foreground"}>
          {r.whatsapp_status}
        </p>
        {r.whatsapp_error && <p className="max-w-[260px] text-xs text-need">{r.whatsapp_error}</p>}
        {!r.agent_enabled && <p className="text-xs text-muted-foreground">agent paused</p>}
      </td>
      <td className="px-3 py-2.5 font-mono text-[12px]">{ago(r.last_customer_activity)}</td>
      <td className="px-3 py-2.5 text-right font-mono tabular-nums">{r.messages_today}</td>
      <td className="px-3 py-2.5 text-right font-mono tabular-nums">{r.orders_today}</td>
      <td className={`px-3 py-2.5 text-right font-mono tabular-nums ${r.failed_messages_24h > 0 ? "text-need" : ""}`}>
        {r.failed_messages_24h}
      </td>
      <td className={`px-3 py-2.5 text-right font-mono tabular-nums ${r.escalations_open > 0 ? "text-ai" : ""}`}>
        {r.escalations_open}
      </td>
      <td className="px-3 py-2.5 text-right font-mono tabular-nums">
        {r.ai_conversations_this_month} / {r.plan_limit}
      </td>
    </tr>
  )
}
