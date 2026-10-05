"use client"

import * as React from "react"
import { useQuery } from "@tanstack/react-query"

import { CounterBills } from "@/components/staff/counter-bills"
import { LinkScreen } from "@/components/staff/link-screen"
import { staffOpenOrders, type TableOrder } from "@/services/staff/staff.service"

function isUnlinked(err: unknown) {
  const status = (err as { response?: { status?: number } })?.response?.status
  return status === 401 || status === 403
}

function money(n: number) {
  return `Rs ${Math.round(n).toLocaleString("en-US")}`
}

function orderTotal(o: TableOrder) {
  return o.items.reduce((sum, i) => sum + i.price * i.qty, 0)
}

/** One line for where a table is, from the bill side first, then the kitchen side. */
function tableStatus(list: TableOrder[]) {
  const billed = list.filter((o) => o.status === "billed")
  if (billed.length > 0) {
    return billed.every((o) => o.bill_printed_at)
      ? { text: "Bill printed", tone: "done" as const }
      : { text: "Bill to print", tone: "action" as const }
  }
  if (list.some((o) => o.status === "sent" && o.kitchen_status === "ready")) return { text: "Food ready", tone: "ready" as const }
  if (list.some((o) => o.status === "sent" && o.kitchen_status === "cooking")) return { text: "Cooking", tone: "plain" as const }
  if (list.some((o) => o.status === "sent")) return { text: "In kitchen", tone: "plain" as const }
  return { text: "Served", tone: "plain" as const }
}

const TONE: Record<"done" | "action" | "ready" | "plain", string> = {
  done: "border-border",
  action: "border-amber-500",
  ready: "border-green-600",
  plain: "border-border",
}

/** The counter screen: bills to print, every table with its items and prices, and the bills already printed. */
export function CounterBoard({ restaurant }: { restaurant: string }) {
  const orders = useQuery({
    queryKey: ["counter", "orders"],
    queryFn: staffOpenOrders,
    refetchInterval: 4000,
    retry: false,
  })

  if (orders.isError && isUnlinked(orders.error)) {
    return <LinkScreen restaurant={restaurant} kind="counter" onLinked={() => orders.refetch()} />
  }

  const byTable = new Map<number, TableOrder[]>()
  for (const o of orders.data ?? []) {
    byTable.set(o.table_no, [...(byTable.get(o.table_no) ?? []), o])
  }
  const tables = Array.from(byTable.entries()).sort((a, b) => a[0] - b[0])
  const printed = (orders.data ?? []).filter((o) => o.status === "billed" && o.bill_printed_at)

  return (
    <main className="mx-auto flex min-h-svh w-full max-w-5xl flex-col gap-6 px-4 py-5">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Counter</h1>
        <span className="text-base text-muted-foreground">{tables.length} tables open</span>
      </header>

      <CounterBills />

      <section className="grid gap-3">
        <h2 className="text-xl font-semibold">Tables</h2>
        {orders.isPending && <p className="text-base">Loading…</p>}
        {orders.data && tables.length === 0 && <p className="text-base text-muted-foreground">No open tables.</p>}
        <div className="grid gap-4 md:grid-cols-2">
          {tables.map(([tableNo, list]) => {
            const status = tableStatus(list)
            const name = list.find((o) => o.customer_name)?.customer_name
            const subtotal = list.reduce((sum, o) => sum + orderTotal(o), 0)
            return (
              <article key={tableNo} className={`grid gap-3 rounded-2xl border-2 bg-card p-4 ${TONE[status.tone]}`}>
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="text-2xl font-bold">Table {tableNo}</span>
                  <span className="text-base font-medium">{status.text}</span>
                </div>
                {name && <p className="text-base">{name}</p>}
                {list.map((o) => (
                  <div key={o.order_id} className="grid gap-1 border-t border-border pt-2">
                    <p className="text-sm text-muted-foreground">
                      Waiter {o.waiter_name} · {o.status === "served" ? "served" : o.kitchen_status === "ready" ? "ready" : o.kitchen_status === "cooking" ? "cooking" : "in kitchen"}
                    </p>
                    <ul className="grid gap-1 text-base">
                      {o.items.map((i) => (
                        <li key={i.name} className="flex justify-between gap-3">
                          <span>{i.qty} × {i.name}</span>
                          <span className="font-mono">{money(i.price * i.qty)}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
                <div className="flex justify-between border-t-2 border-border pt-2 text-lg font-semibold">
                  <span>Total</span>
                  <span className="font-mono">{money(subtotal)}</span>
                </div>
              </article>
            )
          })}
        </div>
      </section>

      <section className="grid gap-3">
        <h2 className="text-xl font-semibold">Printed</h2>
        {printed.length === 0 && <p className="text-base text-muted-foreground">No bills printed yet.</p>}
        {printed.map((o) => (
          <div key={o.order_id} className="flex flex-wrap justify-between gap-2 rounded-xl border border-border bg-card p-3 text-base">
            <span>Table {o.table_no}{o.customer_name ? ` · ${o.customer_name}` : ""}</span>
            <span className="font-mono">{money(orderTotal(o))}</span>
          </div>
        ))}
      </section>
    </main>
  )
}
