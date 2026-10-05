"use client"

import * as React from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  markPaidCash,
  markServed,
  requestBill,
  sendTableOrder,
  staffMenu,
  staffOpenOrders,
  staffTables,
  type TableOrder,
  type TableState,
} from "@/services/staff/staff.service"

const STATUS_TEXT: Record<TableState["status"], string> = {
  free: "Free",
  sent: "Order in kitchen",
  ready: "Food ready",
  served: "Served",
  bill: "Bill printed",
}

const TILE_STYLE: Record<TableState["status"], string> = {
  free: "border-border bg-card",
  sent: "border-amber-500 bg-card",
  ready: "border-green-600 bg-green-50 dark:bg-green-950/40",
  served: "border-green-600 bg-card",
  bill: "border-foreground bg-card",
}

function errorText(err: unknown, fallback: string) {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback
}

function money(n: number) {
  return `Rs ${Math.round(n).toLocaleString("en-US")}`
}

/** The waiter's home: a big tile for each table. Tapping one opens that table. */
export function WaiterScreen() {
  const [tableNo, setTableNo] = React.useState<number | null>(null)
  const tables = useQuery({ queryKey: ["staff", "tables"], queryFn: staffTables, refetchInterval: 5000 })

  if (tableNo !== null) return <TableScreen tableNo={tableNo} onDone={() => setTableNo(null)} />

  return (
    <div className="grid gap-4">
      <p className="text-base text-muted-foreground">Tap a table.</p>
      {tables.isPending && <p className="text-base">Loading tables…</p>}
      {tables.data?.length === 0 && (
        <p className="text-base">No tables yet. Ask the owner to set up the tables.</p>
      )}
      <div className="grid grid-cols-2 gap-4">
        {tables.data?.map((t) => (
          <button
            key={t.table_no}
            type="button"
            onClick={() => setTableNo(t.table_no)}
            className={`flex min-h-32 flex-col justify-between rounded-2xl border-2 p-4 text-left ${TILE_STYLE[t.status]}`}
          >
            <span className="text-3xl font-bold">Table {t.table_no}</span>
            <span className="text-base font-medium">{STATUS_TEXT[t.status]}</span>
            {t.total > 0 && <span className="font-mono text-base">{money(t.total)}</span>}
          </button>
        ))}
      </div>
    </div>
  )
}

/**
 * One table. The big button at the bottom always does the next step:
 * send the new items, serve ready food, print the bill, or take the cash.
 */
function TableScreen({ tableNo, onDone }: { tableNo: number; onDone: () => void }) {
  const queryClient = useQueryClient()
  const menu = useQuery({ queryKey: ["staff", "menu"], queryFn: staffMenu, staleTime: 60_000 })
  const orders = useQuery({ queryKey: ["staff", "orders"], queryFn: staffOpenOrders, refetchInterval: 5000 })
  const [cart, setCart] = React.useState<Record<string, number>>({})
  const [category, setCategory] = React.useState<string | null>(null)
  const [billTotal, setBillTotal] = React.useState<number | null>(null)

  const here: TableOrder[] = (orders.data ?? []).filter((o) => o.table_no === tableNo)
  const waiting = here.filter((o) => o.status === "sent")
  const billed = here.some((o) => o.status === "billed")
  const hasServable = waiting.length > 0
  const canBill = waiting.length > 0 || here.some((o) => o.status === "served")

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["staff", "orders"] })
    queryClient.invalidateQueries({ queryKey: ["staff", "tables"] })
  }

  const send = useMutation({
    mutationFn: () => sendTableOrder(tableNo, Object.entries(cart).map(([name, qty]) => ({ name, qty }))),
    onSuccess: () => { setCart({}); toast.success("Sent to the kitchen."); refresh() },
    onError: (err) => toast.error(errorText(err, "Could not send. Try again.")),
  })
  const served = useMutation({
    mutationFn: (id: string) => markServed(id),
    onSuccess: () => { toast.success("Marked served."); refresh() },
    onError: (err) => toast.error(errorText(err, "Could not update.")),
  })
  const bill = useMutation({
    mutationFn: () => requestBill(tableNo),
    onSuccess: (r) => { setBillTotal(r.total); toast.success("Bill sent to the printer."); refresh() },
    onError: (err) => toast.error(errorText(err, "Could not print the bill.")),
  })
  const paid = useMutation({
    mutationFn: () => markPaidCash(tableNo),
    onSuccess: () => { toast.success(`Table ${tableNo} is paid and free.`); refresh(); onDone() },
    onError: (err) => toast.error(errorText(err, "Could not mark paid.")),
  })

  const cartLines = Object.entries(cart)
  const cartCount = cartLines.reduce((n, [, q]) => n + q, 0)
  const cartTotal = cartLines.reduce((sum, [name, qty]) => sum + (menu.data?.find((m) => m.name === name)?.price ?? 0) * qty, 0)
  const categories = Array.from(new Set((menu.data ?? []).map((m) => m.category)))
  const activeCategory = category ?? categories[0] ?? null
  const shown = (menu.data ?? []).filter((m) => m.category === activeCategory)

  // The one big action, in order of what the waiter needs to do next.
  type Action = { label: string; run: () => void; busy: boolean; variant?: "default" | "outline" }
  let action: Action | null = null
  if (billTotal !== null) action = { label: "Customer paid cash", run: () => paid.mutate(), busy: paid.isPending }
  else if (cartCount > 0) action = { label: `Send ${cartCount} to kitchen · ${money(cartTotal)}`, run: () => send.mutate(), busy: send.isPending }
  else if (hasServable) action = { label: "Mark food served", run: () => served.mutate(waiting[0].order_id), busy: served.isPending }
  else if (billed) action = { label: "Customer paid cash", run: () => paid.mutate(), busy: paid.isPending }
  else if (canBill) action = { label: "Print bill", run: () => bill.mutate(), busy: bill.isPending, variant: "outline" }

  return (
    <div className="flex flex-col gap-4 pb-32">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-3xl font-bold">Table {tableNo}</h2>
        <Button variant="outline" className="min-h-12 px-5 text-base" onClick={onDone} disabled={cartCount > 0}>
          All tables
        </Button>
      </div>

      {billTotal !== null ? (
        <section className="grid gap-3 rounded-2xl border-2 border-foreground bg-card p-5 text-center">
          <p className="text-base">Bill total</p>
          <p className="font-mono text-4xl font-bold">{money(billTotal)}</p>
          <p className="text-base">Give the printed bill to the customer. Cash only.</p>
        </section>
      ) : (
        <>
          {here.length > 0 && (
            <section className="grid gap-2">
              {here.map((o) => (
                <article key={o.order_id} className="rounded-2xl border-2 border-border bg-card p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-base font-semibold">
                      {o.status === "billed" ? "Billed" : o.kitchen_status === "ready" ? "Ready now" : o.kitchen_status === "cooking" ? "Cooking" : "In kitchen"}
                    </span>
                    {o.status === "sent" && o.kitchen_status === "ready" && (
                      <Button className="min-h-12 px-4 text-base" onClick={() => served.mutate(o.order_id)} disabled={served.isPending}>
                        Served
                      </Button>
                    )}
                  </div>
                  <ul className="mt-2 text-base">
                    {o.items.map((i) => <li key={i.name}>{i.qty} × {i.name}</li>)}
                  </ul>
                </article>
              ))}
            </section>
          )}

          <section className="grid gap-3">
            <div className="flex gap-2 overflow-x-auto pb-1">
              {categories.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setCategory(c)}
                  className={`min-h-12 shrink-0 rounded-full border-2 px-4 text-base font-medium ${c === activeCategory ? "border-foreground bg-foreground text-background" : "border-border bg-card"}`}
                >
                  {c}
                </button>
              ))}
            </div>
            {menu.isPending && <p className="text-base">Loading menu…</p>}
            <div className="grid grid-cols-2 gap-3">
              {shown.map((m) => (
                <button
                  key={m.name}
                  type="button"
                  disabled={m.sold_out}
                  onClick={() => setCart((c) => ({ ...c, [m.name]: (c[m.name] ?? 0) + 1 }))}
                  className="flex min-h-24 flex-col justify-between rounded-2xl border-2 border-border bg-card p-3 text-left disabled:opacity-40"
                >
                  <span className="text-base font-semibold leading-tight">
                    {m.name}
                    {cart[m.name] ? <span className="ml-2 rounded-full bg-foreground px-2 text-sm text-background">{cart[m.name]}</span> : null}
                  </span>
                  <span className="font-mono text-base">{m.sold_out ? "Sold out today" : money(m.price)}</span>
                </button>
              ))}
            </div>
          </section>

          {cartLines.length > 0 && (
            <section className="grid gap-2 rounded-2xl border-2 border-border bg-card p-4">
              <h3 className="text-base font-semibold">New items</h3>
              {cartLines.map(([name, qty]) => (
                <div key={name} className="flex items-center justify-between gap-2">
                  <span className="text-base">{name}</span>
                  <div className="flex items-center gap-3">
                    <Button variant="outline" className="h-12 w-12 text-xl" aria-label={`Remove one ${name}`} onClick={() => setCart((c) => { const n = { ...c }; n[name] -= 1; if (n[name] <= 0) delete n[name]; return n })}>−</Button>
                    <span className="w-6 text-center font-mono text-lg">{qty}</span>
                    <Button variant="outline" className="h-12 w-12 text-xl" aria-label={`Add one ${name}`} onClick={() => setCart((c) => ({ ...c, [name]: c[name] + 1 }))}>+</Button>
                  </div>
                </div>
              ))}
            </section>
          )}
        </>
      )}

      {/* The one big button, pinned to the bottom of the screen. */}
      <div className="fixed inset-x-0 bottom-0 border-t-2 border-border bg-background p-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
        {action ? (
          <Button className="min-h-16 w-full text-lg font-semibold" variant={action.variant} onClick={action.run} disabled={action.busy}>
            {action.busy ? "Working…" : action.label}
          </Button>
        ) : (
          <p className="text-center text-base text-muted-foreground">Tap dishes to start the order.</p>
        )}
      </div>
    </div>
  )
}
