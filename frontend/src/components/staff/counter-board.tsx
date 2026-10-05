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

function kitchenText(o: TableOrder) {
  if (o.status === "billed") return "Bill printed"
  if (o.status === "served") return "Served"
  if (o.kitchen_status === "ready") return "Food ready"
  if (o.kitchen_status === "cooking") return "Cooking"
  return "In kitchen"
}

/** The counter screen. Every open order by table, so the cashier knows what's on each table. Read only for now. */
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

  return (
    <main className="mx-auto flex min-h-svh w-full max-w-4xl flex-col gap-4 px-4 py-5">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Counter</h1>
        <span className="text-base text-muted-foreground">{tables.length} tables open</span>
      </header>

      <CounterBills />

      {orders.isPending && <p className="text-base">Loading…</p>}
      {orders.data && tables.length === 0 && <p className="text-base text-muted-foreground">No open tables.</p>}

      <div className="grid gap-4 sm:grid-cols-2">
        {tables.map(([tableNo, list]) => (
          <article key={tableNo} className="grid gap-2 rounded-2xl border-2 border-border bg-card p-4">
            <div className="flex items-center justify-between">
              <span className="text-2xl font-bold">Table {tableNo}</span>
              <span className="font-mono text-base">{list.some((o) => o.status === "billed") ? "Bill printed" : "Open"}</span>
            </div>
            {list.map((o) => (
              <div key={o.order_id} className="border-t border-border pt-2">
                <p className="text-sm font-medium">{kitchenText(o)} · {o.waiter_name}</p>
                <ul className="text-base">
                  {o.items.map((i) => <li key={i.name}>{i.qty} × {i.name}</li>)}
                </ul>
              </div>
            ))}
          </article>
        ))}
      </div>
    </main>
  )
}
