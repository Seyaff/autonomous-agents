"use client"

import * as React from "react"
import { useQuery } from "@tanstack/react-query"

import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { useAuth } from "@/components/providers/auth-provider"
import { useCurrentTenant } from "@/hooks/tenant/use-current-tenant"
import { formatMoney } from "@/lib/currency"
import { USE_MOCKS } from "@/lib/mocks"
import { getCustomer, listCustomers, type CustomerDetail } from "@/services/customers/customers.service"

function when(iso: string | null) {
  if (!iso) return "—"
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })
}

/** Everyone who has ordered, and what the agent remembers about each. */
export default function CustomersPage() {
  const { activeTenantId } = useAuth()
  const { data: tenant } = useCurrentTenant()
  const currency = tenant?.currency ?? "USD"
  const [search, setSearch] = React.useState("")
  const [selected, setSelected] = React.useState<string | null>(null)

  const enabled = !USE_MOCKS && !!activeTenantId
  const list = useQuery({
    queryKey: ["customers", search],
    queryFn: () => listCustomers(search.trim()),
    enabled,
  })
  const detail = useQuery({
    queryKey: ["customers", "detail", selected],
    queryFn: () => getCustomer(selected as string),
    enabled: enabled && !!selected,
  })

  const rows = list.data?.customers ?? []

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-border bg-card px-4 py-2">
        <div>
          <h1 className="text-sm font-medium">Customers</h1>
          <p className="font-mono text-[11px] text-muted-foreground">
            {list.data ? `${list.data.total} customers` : "Who has ordered, and what the agent remembers"}
          </p>
        </div>
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search name or phone"
          className="w-64"
        />
      </div>

      <div className="flex-1 overflow-auto p-4">
        {USE_MOCKS ? (
          <p className="font-mono text-[12px] text-muted-foreground">Customers need the live backend.</p>
        ) : (
          <table className="w-full min-w-[640px] text-sm">
            <thead className="text-left font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">Customer</th>
                <th className="px-3 py-2 text-right font-medium">Orders</th>
                <th className="px-3 py-2 text-right font-medium">Spent</th>
                <th className="px-3 py-2 font-medium">Last order</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr
                  key={c.customer_phone}
                  onClick={() => setSelected(c.customer_phone)}
                  className="cursor-pointer border-t border-border hover:bg-muted"
                >
                  <td className="px-3 py-2.5">
                    <p className="font-medium">{c.name ?? "Unknown"}</p>
                    <p className="font-mono text-[11px] text-muted-foreground">{c.customer_phone}</p>
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono tabular-nums">{c.total_orders}</td>
                  <td className="px-3 py-2.5 text-right font-mono tabular-nums">
                    {formatMoney(c.total_spent, c.currency ?? currency)}
                  </td>
                  <td className="px-3 py-2.5 font-mono text-[12px]">{when(c.last_order_at)}</td>
                </tr>
              ))}
              {list.isSuccess && rows.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-3 py-8 text-center font-mono text-[12px] text-muted-foreground">
                    {search ? "No customer matches that search." : "No customers yet. They appear here after their first order."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      <Sheet open={!!selected} onOpenChange={(open) => { if (!open) setSelected(null) }}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-md">
          <SheetHeader>
            <SheetTitle>{detail.data?.customer.name ?? selected ?? "Customer"}</SheetTitle>
            <SheetDescription className="font-mono">{selected}</SheetDescription>
          </SheetHeader>
          {detail.isPending && <p className="px-4 font-mono text-[12px] text-muted-foreground">Loading…</p>}
          {detail.data && <CustomerBody d={detail.data} currency={currency} />}
        </SheetContent>
      </Sheet>
    </div>
  )
}

function CustomerBody({ d, currency }: { d: CustomerDetail; currency: string }) {
  const c = d.customer
  return (
    <div className="space-y-5 px-4 pb-6">
      <div className="grid grid-cols-3 gap-2">
        <Stat label="Orders" value={String(c.total_orders)} />
        <Stat label="Delivered" value={String(c.delivered_orders)} />
        <Stat label="Spent" value={formatMoney(c.total_spent, currency)} />
      </div>
      <p className="font-mono text-[12px] text-muted-foreground">
        Customer since {when(c.first_order_at)} · last order {when(c.last_order_at)}
      </p>

      <section className="space-y-2">
        <h2 className="font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground">Usually orders</h2>
        {c.favourites.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing yet.</p>
        ) : (
          <ul className="flex flex-wrap gap-1.5">
            {c.favourites.map((f) => (
              <Badge key={f.name} variant="secondary">
                {f.name} × {f.quantity}
              </Badge>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
          What the agent remembers
        </h2>
        {c.facts.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing noted yet. Preferences and allergies appear here as customers mention them.</p>
        ) : (
          <ul className="space-y-1.5">
            {c.facts.map((f) => (
              <li key={`${f.kind}-${f.key}`} className="text-sm">
                <span className="mr-2 font-mono text-[11px] uppercase text-muted-foreground">{f.kind}</span>
                {f.value}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground">Recent orders</h2>
        <ul className="divide-y divide-border rounded-md border border-border">
          {d.recent_orders.map((o) => (
            <li key={o.order_id} className="flex items-start justify-between gap-3 px-3 py-2 text-sm">
              <div className="min-w-0">
                <p className="font-mono text-[12px]">{o.order_id}</p>
                <p className="truncate text-xs text-muted-foreground">
                  {o.items.map((i) => `${i.quantity}× ${i.name}`).join(", ")}
                </p>
              </div>
              <div className="shrink-0 text-right">
                <p className="font-mono tabular-nums">{formatMoney(o.total_amount, o.currency ?? currency)}</p>
                <p className="font-mono text-[11px] text-muted-foreground">{o.status}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border p-2.5">
      <p className="font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">{label}</p>
      <p className="mt-0.5 font-mono text-sm tabular-nums">{value}</p>
    </div>
  )
}
