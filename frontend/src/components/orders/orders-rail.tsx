"use client"

import { Ticket } from "@/components/console/ticket"
import { Skeleton } from "@/components/ui/skeleton"
import { ORDER_STATUS_DISPLAY, type OrderStatus } from "@/lib/status"
import type { RailOrder } from "@/hooks/console/use-rail"

const COLUMNS: OrderStatus[] = [
  "pending",
  "accepted",
  "preparing",
  "out_for_delivery",
  "delivered",
  "cancelled",
]

export function OrdersRail({
  orders,
  currency,
  isLoading,
  onAdvance,
}: {
  orders: RailOrder[]
  currency: string
  isLoading: boolean
  onAdvance: (order: RailOrder, next: OrderStatus) => void
}) {
  return (
    <div className="flex h-full gap-3 overflow-x-auto p-4">
      {COLUMNS.map((status) => {
        const items = orders.filter((o) => o.status === status)
        const { label } = ORDER_STATUS_DISPLAY[status]
        return (
          <div key={status} className="flex w-64 shrink-0 flex-col gap-3">
            <p className="shrink-0 font-mono text-[11px] tracking-[.08em] text-muted-foreground uppercase">
              {label} · {items.length}
            </p>
            <div className="flex flex-1 flex-col gap-3 overflow-y-auto">
              {isLoading ? (
                <>
                  <Skeleton className="h-40 w-full" />
                  <Skeleton className="h-40 w-full" />
                </>
              ) : items.length === 0 ? (
                <p className="font-mono text-xs text-muted-foreground">None</p>
              ) : (
                items.map((order) => (
                  <Ticket
                    key={order.order_id}
                    order={order}
                    currency={currency}
                    onAdvance={(next) => onAdvance(order, next)}
                  />
                ))
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
