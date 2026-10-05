"use client"

import * as React from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  kitchenStep,
  markPaidCash,
  markServed,
  requestBill,
  sendTableOrder,
  staffMe,
  staffMenu,
  staffOpenOrders,
  staffRoster,
  staffSignIn,
  staffSignOut,
  staffTables,
  type RosterEntry,
  type StaffMember,
  type TableOrder,
  type TableState,
} from "@/services/staff/staff.service"

const ROLE_LABEL: Record<string, string> = { waiter: "Waiter", reception: "Reception", kitchen: "Kitchen" }
const TABLE_LABEL: Record<TableState["status"], string> = {
  free: "Free",
  sent: "Sent to kitchen",
  ready: "Food ready",
  served: "Served",
  bill: "Bill printed",
}

function errorText(err: unknown, fallback: string) {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback
}

function money(n: number) {
  return `Rs ${Math.round(n).toLocaleString("en-US")}`
}

/** The staff app for one restaurant: sign-in, then the waiter, kitchen or reception screen. */
export function StaffApp({ restaurant }: { restaurant: string }) {
  const queryClient = useQueryClient()
  const me = useQuery({ queryKey: ["staff", "me"], queryFn: staffMe, retry: false })
  const roster = useQuery({
    queryKey: ["staff", "roster", restaurant],
    queryFn: () => staffRoster(restaurant),
    enabled: me.isError,
  })

  const [picked, setPicked] = React.useState<RosterEntry | null>(null)
  const [pin, setPin] = React.useState("")
  const [pinError, setPinError] = React.useState<string | null>(null)

  const signIn = useMutation({
    mutationFn: (args: { staff_id: string; pin: string }) => staffSignIn(restaurant, args.staff_id, args.pin),
    onSuccess: (staff: StaffMember) => {
      queryClient.setQueryData(["staff", "me"], staff)
      setPicked(null)
      setPin("")
      setPinError(null)
    },
    onError: (err) => {
      setPin("")
      setPinError(errorText(err, "Could not sign in. Try again."))
    },
  })

  const pressKey = (k: string) => {
    if (!picked || signIn.isPending) return
    if (k === "⌫") {
      setPin((p) => p.slice(0, -1))
      return
    }
    const next = (pin + k).slice(0, 4)
    setPin(next)
    setPinError(null)
    if (next.length === 4) signIn.mutate({ staff_id: picked.staff_id, pin: next })
  }

  const signOut = async () => {
    try {
      await staffSignOut()
    } finally {
      queryClient.setQueryData(["staff", "me"], null)
      queryClient.removeQueries({ queryKey: ["staff", "me"] })
      queryClient.invalidateQueries({ queryKey: ["staff", "roster", restaurant] })
    }
  }

  if (me.isPending) return <Shell title="Siyaf staff"><p className="text-sm text-muted-foreground">Loading…</p></Shell>

  if (me.data) {
    return (
      <Shell title={`${me.data.name} · ${ROLE_LABEL[me.data.role] ?? me.data.role}`} onSignOut={signOut}>
        {me.data.role === "waiter" && <WaiterScreen />}
        {me.data.role === "kitchen" && <KitchenScreen canCook />}
        {me.data.role === "reception" && <KitchenScreen canCook={false} />}
      </Shell>
    )
  }

  if (picked) {
    return (
      <Shell title="Enter your PIN" onBack={() => { setPicked(null); setPin(""); setPinError(null) }}>
        <div className="mx-auto flex max-w-xs flex-col items-center gap-4">
          <p className="text-sm text-muted-foreground">{picked.name}</p>
          <div className="font-mono text-2xl tracking-[0.4em]" aria-live="polite">{pin ? "•".repeat(pin.length) : " "}</div>
          {pinError && <p role="alert" className="text-center text-sm text-destructive">{pinError}</p>}
          <div className="grid grid-cols-3 gap-3">
            {["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "⌫"].map((k, i) => (
              <button
                key={i}
                type="button"
                disabled={!k || signIn.isPending}
                onClick={() => pressKey(k)}
                aria-label={k === "⌫" ? "Delete digit" : k || undefined}
                className="h-16 w-16 rounded-xl border border-border bg-card text-lg disabled:opacity-0"
              >
                {k}
              </button>
            ))}
          </div>
        </div>
      </Shell>
    )
  }

  return (
    <Shell title="Who is signing in?">
      {roster.isPending && <p className="text-sm text-muted-foreground">Loading names…</p>}
      {roster.isError && <p role="alert" className="text-sm text-destructive">This restaurant link doesn&apos;t work.</p>}
      {roster.data && roster.data.length === 0 && (
        <p className="text-sm text-muted-foreground">No staff yet. The owner adds people on the Staff page.</p>
      )}
      <div className="grid gap-2">
        {roster.data?.map((r) => (
          <button
            key={r.staff_id}
            type="button"
            disabled={r.locked}
            onClick={() => { setPicked(r); setPin(""); setPinError(null) }}
            className="flex min-h-14 items-center justify-between rounded-xl border border-border bg-card px-4 text-left disabled:opacity-50"
          >
            <span className="font-medium">{r.name}</span>
            <span className="text-xs text-muted-foreground">{r.locked ? "Locked. Ask the owner." : ROLE_LABEL[r.role]}</span>
          </button>
        ))}
      </div>
    </Shell>
  )
}

function Shell({ title, children, onBack, onSignOut }: {
  title: string
  children: React.ReactNode
  onBack?: () => void
  onSignOut?: () => void
}) {
  return (
    <main className="mx-auto flex min-h-svh w-full max-w-xl flex-col gap-4 px-4 py-6">
      <header className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {onBack && <Button variant="ghost" onClick={onBack}>← Back</Button>}
          <h1 className="text-base font-semibold">{title}</h1>
        </div>
        {onSignOut && <Button variant="outline" onClick={onSignOut}>Sign out</Button>}
      </header>
      {children}
    </main>
  )
}

// ---------------------------------------------------------------------------
// Waiter: tables, order, bill
// ---------------------------------------------------------------------------
function WaiterScreen() {
  const [tableNo, setTableNo] = React.useState<number | null>(null)
  const tables = useQuery({ queryKey: ["staff", "tables"], queryFn: staffTables, refetchInterval: 5000 })

  if (tableNo !== null) return <TableScreen tableNo={tableNo} onBack={() => setTableNo(null)} />

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      {tables.isPending && <p className="col-span-full text-sm text-muted-foreground">Loading tables…</p>}
      {tables.data?.length === 0 && <p className="col-span-full text-sm text-muted-foreground">No tables set up. The owner sets the table count.</p>}
      {tables.data?.map((t) => (
        <button
          key={t.table_no}
          type="button"
          onClick={() => setTableNo(t.table_no)}
          className="flex min-h-24 flex-col justify-between rounded-xl border border-border bg-card p-3 text-left"
        >
          <span className="font-semibold">Table {t.table_no}</span>
          <span className={`text-xs ${t.status === "ready" ? "text-green-600" : "text-muted-foreground"}`}>
            {TABLE_LABEL[t.status]}
          </span>
          {t.total > 0 && <span className="font-mono text-xs">{money(t.total)}</span>}
        </button>
      ))}
    </div>
  )
}

function TableScreen({ tableNo, onBack }: { tableNo: number; onBack: () => void }) {
  const queryClient = useQueryClient()
  const menu = useQuery({ queryKey: ["staff", "menu"], queryFn: staffMenu, staleTime: 60_000 })
  const orders = useQuery({
    queryKey: ["staff", "orders"],
    queryFn: staffOpenOrders,
    refetchInterval: 5000,
  })
  const [cart, setCart] = React.useState<Record<string, number>>({})
  const [billTotal, setBillTotal] = React.useState<number | null>(null)

  const here = (orders.data ?? []).filter((o: TableOrder) => o.table_no === tableNo)
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["staff", "orders"] })
    queryClient.invalidateQueries({ queryKey: ["staff", "tables"] })
  }

  const send = useMutation({
    mutationFn: () => sendTableOrder(tableNo, Object.entries(cart).map(([name, qty]) => ({ name, qty }))),
    onSuccess: () => {
      setCart({})
      toast.success(`Sent. Slip and kitchen ticket are printing for table ${tableNo}.`)
      refresh()
    },
    onError: (err) => toast.error(errorText(err, "Could not send the order.")),
  })
  const served = useMutation({
    mutationFn: (id: string) => markServed(id),
    onSuccess: () => { toast.success("Marked served."); refresh() },
    onError: (err) => toast.error(errorText(err, "Could not update.")),
  })
  const bill = useMutation({
    mutationFn: () => requestBill(tableNo),
    onSuccess: (res) => { setBillTotal(res.total); toast.success("Bill sent to the reception printer."); refresh() },
    onError: (err) => toast.error(errorText(err, "Could not print the bill.")),
  })
  const paid = useMutation({
    mutationFn: () => markPaidCash(tableNo),
    onSuccess: () => { setBillTotal(null); toast.success(`Table ${tableNo} paid in cash.`); refresh() },
    onError: (err) => toast.error(errorText(err, "Could not mark paid.")),
  })

  const lines = Object.entries(cart)
  const cartTotal = lines.reduce((sum, [name, qty]) => sum + (menu.data?.find((m) => m.name === name)?.price ?? 0) * qty, 0)
  const categories = Array.from(new Set((menu.data ?? []).map((m) => m.category)))
  const canBill = here.some((o) => o.status === "sent" || o.status === "served")
  const canPay = here.some((o) => o.status === "billed")

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <Button variant="ghost" onClick={onBack}>← Tables</Button>
        <h2 className="font-semibold">Table {tableNo}</h2>
      </div>

      {here.length > 0 && (
        <section className="grid gap-2">
          {here.map((o) => (
            <article key={o.order_id} className="rounded-xl border border-border bg-card p-3 text-sm">
              <div className="flex justify-between">
                <span className="font-mono text-xs text-muted-foreground">{o.order_id}</span>
                <span className="text-xs">{o.kitchen_status === "ready" ? "Ready" : o.kitchen_status === "cooking" ? "Cooking" : "Waiting in kitchen"}</span>
              </div>
              <ul className="mt-1">
                {o.items.map((i) => <li key={i.name}>{i.qty} × {i.name}</li>)}
              </ul>
              {o.status === "sent" && (
                <Button className="mt-2 w-full" variant={o.kitchen_status === "ready" ? "default" : "outline"} onClick={() => served.mutate(o.order_id)} disabled={served.isPending}>
                  {o.kitchen_status === "ready" ? "Food ready: mark served" : "Mark served"}
                </Button>
              )}
            </article>
          ))}
        </section>
      )}

      {billTotal === null ? (
        <>
          <section className="grid gap-4">
            {categories.map((cat) => (
              <div key={cat} className="grid gap-2">
                <h3 className="text-xs uppercase tracking-wide text-muted-foreground">{cat}</h3>
                {(menu.data ?? []).filter((m) => m.category === cat).map((m) => (
                  <button
                    key={m.name}
                    type="button"
                    disabled={m.sold_out}
                    onClick={() => setCart((c) => ({ ...c, [m.name]: (c[m.name] ?? 0) + 1 }))}
                    className="flex min-h-12 items-center justify-between rounded-xl border border-border bg-card px-3 text-left disabled:opacity-40"
                  >
                    <span>{m.name}{m.sold_out && <span className="ml-2 text-xs text-muted-foreground">Sold out today</span>}</span>
                    <span className="font-mono text-sm">{money(m.price)}</span>
                  </button>
                ))}
              </div>
            ))}
            {menu.isPending && <p className="text-sm text-muted-foreground">Loading menu…</p>}
          </section>

          <section className="grid gap-2 rounded-xl border border-border bg-card p-3">
            <h3 className="font-medium">New items</h3>
            {lines.length === 0 && <p className="text-sm text-muted-foreground">Tap dishes to add them.</p>}
            {lines.map(([name, qty]) => (
              <div key={name} className="flex items-center justify-between gap-2">
                <span className="text-sm">{name}</span>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" onClick={() => setCart((c) => { const n = { ...c }; n[name] -= 1; if (n[name] <= 0) delete n[name]; return n })}>−</Button>
                  <span className="w-6 text-center font-mono">{qty}</span>
                  <Button variant="outline" size="sm" onClick={() => setCart((c) => ({ ...c, [name]: c[name] + 1 }))}>+</Button>
                </div>
              </div>
            ))}
            <div className="flex justify-between border-t border-border pt-2 text-sm">
              <span className="text-muted-foreground">Total</span>
              <span className="font-mono">{money(cartTotal)}</span>
            </div>
            <Button onClick={() => send.mutate()} disabled={lines.length === 0 || send.isPending}>Send to kitchen</Button>
          </section>

          <div className="flex flex-wrap gap-2">
            <Button variant="outline" className="flex-1" onClick={() => bill.mutate()} disabled={!canBill || bill.isPending}>Print bill</Button>
            <Button className="flex-1" onClick={() => paid.mutate()} disabled={!canPay || paid.isPending}>Mark paid (cash)</Button>
          </div>
        </>
      ) : (
        <section className="grid gap-3 rounded-xl border border-border bg-card p-4 text-center">
          <p className="text-sm text-muted-foreground">Bill for table {tableNo}</p>
          <p className="font-mono text-2xl">{money(billTotal)}</p>
          <p className="text-sm">Take the printed bill to the table. Cash only.</p>
          <Button onClick={() => paid.mutate()} disabled={paid.isPending}>Mark paid (cash)</Button>
        </section>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Kitchen and reception: open tickets
// ---------------------------------------------------------------------------
function KitchenScreen({ canCook }: { canCook: boolean }) {
  const queryClient = useQueryClient()
  const orders = useQuery({ queryKey: ["staff", "orders"], queryFn: staffOpenOrders, refetchInterval: 5000 })
  const step = useMutation({
    mutationFn: (args: { id: string; to: "cooking" | "ready" }) => kitchenStep(args.id, args.to),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["staff", "orders"] }),
    onError: (err) => toast.error(errorText(err, "Could not update the ticket.")),
  })
  const tickets = (orders.data ?? []).filter((o) => o.status === "sent")

  if (orders.isPending) return <p className="text-sm text-muted-foreground">Loading tickets…</p>
  if (tickets.length === 0) return <p className="text-sm text-muted-foreground">No open tickets.</p>

  return (
    <div className="grid gap-3">
      {tickets.map((o) => (
        <article key={o.order_id} className="grid gap-2 rounded-xl border border-border bg-card p-3">
          <div className="flex items-center justify-between">
            <strong>Table {o.table_no}</strong>
            <span className="text-xs text-muted-foreground">{o.kitchen_status === "new" ? "New" : o.kitchen_status === "cooking" ? "Cooking" : "Ready"} · {o.waiter_name}</span>
          </div>
          <ul className="text-sm">
            {o.items.map((i) => <li key={i.name}>{i.qty} × {i.name}</li>)}
          </ul>
          {canCook && o.kitchen_status === "new" && (
            <Button onClick={() => step.mutate({ id: o.order_id, to: "cooking" })} disabled={step.isPending}>Start cooking</Button>
          )}
          {canCook && o.kitchen_status === "cooking" && (
            <Button onClick={() => step.mutate({ id: o.order_id, to: "ready" })} disabled={step.isPending}>Mark ready</Button>
          )}
        </article>
      ))}
    </div>
  )
}
