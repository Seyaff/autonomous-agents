"use client"

import * as React from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { LinkScreen } from "@/components/staff/link-screen"
import { kitchenStep, staffOpenOrders, type TableOrder } from "@/services/staff/staff.service"

function isUnlinked(err: unknown) {
  const status = (err as { response?: { status?: number } })?.response?.status
  return status === 401 || status === 403
}

function minutesSince(iso: string) {
  return Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000))
}

/** The kitchen screen. Open tickets, oldest first. Start cooking, then mark ready. No sign-in needed. */
export function KitchenBoard({ restaurant }: { restaurant: string }) {
  const queryClient = useQueryClient()
  const orders = useQuery({
    queryKey: ["kitchen", "orders"],
    queryFn: staffOpenOrders,
    refetchInterval: 4000,
    retry: false,
  })
  const step = useMutation({
    mutationFn: (args: { id: string; to: "cooking" | "ready" }) => kitchenStep(args.id, args.to),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["kitchen", "orders"] }),
    onError: (err) => toast.error((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Could not update the ticket."),
  })

  if (orders.isError && isUnlinked(orders.error)) {
    return <LinkScreen restaurant={restaurant} kind="kitchen" onLinked={() => orders.refetch()} />
  }

  const tickets = (orders.data ?? []).filter((o: TableOrder) => o.status === "sent")

  return (
    <main className="mx-auto flex min-h-svh w-full max-w-4xl flex-col gap-4 px-4 py-5">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Kitchen</h1>
        <span className="text-base text-muted-foreground">{tickets.length} open</span>
      </header>

      {orders.isPending && <p className="text-base">Loading tickets…</p>}
      {orders.data && tickets.length === 0 && <p className="text-base text-muted-foreground">No open tickets.</p>}

      <div className="grid gap-4 sm:grid-cols-2">
        {tickets.map((o) => (
          <article
            key={o.order_id}
            className={`grid gap-3 rounded-2xl border-2 p-4 ${o.kitchen_status === "ready" ? "border-green-600" : o.kitchen_status === "cooking" ? "border-amber-500" : "border-border"} bg-card`}
          >
            <div className="flex items-center justify-between">
              <span className="text-2xl font-bold">Table {o.table_no}</span>
              <span className="font-mono text-base text-muted-foreground">{minutesSince(o.created_at)} min</span>
            </div>
            <ul className="text-lg">
              {o.items.map((i) => <li key={i.name}>{i.qty} × {i.name}</li>)}
            </ul>
            <p className="text-sm text-muted-foreground">Waiter {o.waiter_name}</p>
            {o.kitchen_status === "new" && (
              <button
                type="button"
                onClick={() => step.mutate({ id: o.order_id, to: "cooking" })}
                disabled={step.isPending}
                className="min-h-14 rounded-xl bg-foreground text-lg font-semibold text-background disabled:opacity-50"
              >
                Start cooking
              </button>
            )}
            {o.kitchen_status === "cooking" && (
              <button
                type="button"
                onClick={() => step.mutate({ id: o.order_id, to: "ready" })}
                disabled={step.isPending}
                className="min-h-14 rounded-xl bg-green-700 text-lg font-semibold text-white disabled:opacity-50"
              >
                Mark ready
              </button>
            )}
            {o.kitchen_status === "ready" && (
              <p className="rounded-xl bg-green-50 p-3 text-center text-base font-medium text-green-800 dark:bg-green-950/40 dark:text-green-300">
                Ready. Waiter is coming.
              </p>
            )}
          </article>
        ))}
      </div>
    </main>
  )
}
