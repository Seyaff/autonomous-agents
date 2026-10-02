"use client"

import { Ticket } from "@/components/console/ticket"
import { Skeleton } from "@/components/ui/skeleton"
import type { RailOrder } from "@/hooks/console/use-rail"
import type { OrderStatus } from "@/lib/status"

const ACTIVE_STATUSES: OrderStatus[] = ["pending", "accepted", "preparing", "out_for_delivery"]
const DONE_STATUSES: OrderStatus[] = ["delivered", "cancelled"]

export function RailPane({
  orders,
  currency,
  isLoading,
  onAdvance,
  justPrintedId,
}: {
  orders: RailOrder[]
  currency: string
  isLoading: boolean
  onAdvance: (order: RailOrder, next: OrderStatus) => void
  justPrintedId?: string | null
}) {
  const active = ACTIVE_STATUSES.flatMap((status) => orders.filter((o) => o.status === status))
  const done = DONE_STATUSES.flatMap((status) => orders.filter((o) => o.status === status)).slice(0, 5)

  return (
    <div className="flex h-full w-full shrink-0 flex-col overflow-y-auto border-l border-border bg-muted/30 p-3 lg:w-[400px]">
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full" />
          ))}
        </div>
      ) : orders.length === 0 ? (
        <div className="flex flex-1 items-center justify-center">
          <p className="font-mono text-xs text-muted-foreground">
            No orders yet today. They&apos;ll print here as the agent takes them.
          </p>
        </div>
      ) : (
        <>
          <p className="px-1 pb-2 font-mono text-[11px] tracking-[.08em] text-muted-foreground uppercase">
            In progress · {active.length}
          </p>
          <div className="flex flex-col gap-3">
            {active.map((order) => (
              <Ticket
                key={order.order_id}
                order={order}
                currency={currency}
                onAdvance={(next) => onAdvance(order, next)}
                justPrinted={order.order_id === justPrintedId}
              />
            ))}
            {active.length === 0 && (
              <p className="font-mono text-xs text-muted-foreground">Nothing in progress right now.</p>
            )}
          </div>

          {done.length > 0 && (
            <>
              <p className="px-1 pt-4 pb-2 font-mono text-[11px] tracking-[.08em] text-muted-foreground uppercase">
                Completed · {done.length}
              </p>
              <div className="flex flex-col gap-3">
                {done.map((order) => (
                  <Ticket key={order.order_id} order={order} currency={currency} />
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}
