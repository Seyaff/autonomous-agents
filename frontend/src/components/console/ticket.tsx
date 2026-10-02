"use client"

import { cn } from "@/lib/utils"
import { formatMoney } from "@/lib/currency"
import { useNow } from "@/hooks/use-now"
import type { Order } from "@/services/orders/orders.service"
import type { MockOrder } from "@/lib/mock/orders"
import type { OrderStatus } from "@/lib/status"

export type TicketOrder = Order & Partial<Pick<MockOrder, "delivery_fee" | "source" | "eta_minutes">>

const NEXT_ACTION: Partial<Record<OrderStatus, { label: string; next: OrderStatus }>> = {
  pending: { label: "Send to kitchen →", next: "accepted" },
  accepted: { label: "Start preparing →", next: "preparing" },
  preparing: { label: "Out for delivery →", next: "out_for_delivery" },
  out_for_delivery: { label: "Mark delivered →", next: "delivered" },
}

function formatAge(mins: number) {
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  return `${Math.round(mins / 60)}h ago`
}

export function Ticket({
  order,
  currency,
  onAdvance,
  justPrinted,
}: {
  order: TicketOrder
  currency: string
  onAdvance?: (next: OrderStatus) => void
  justPrinted?: boolean
}) {
  const action = NEXT_ACTION[order.status]
  const createdMs = new Date(order.created_at).getTime()
  const now = useNow()

  const ageMinutes = Math.max(0, Math.round((now - createdMs) / 60_000))

  const isLate =
    order.eta_minutes !== undefined &&
    !["delivered", "cancelled"].includes(order.status) &&
    now - createdMs > order.eta_minutes * 60_000

  const lateBy = isLate ? Math.round((now - createdMs) / 60_000 - order.eta_minutes!) : 0

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-[4px] bg-paper px-3 py-3 text-paper-ink shadow-sm",
        isLate && "border-l-4 border-need",
        justPrinted && "motion-safe:animate-[print-in_0.4s_ease-out]"
      )}
    >
      <div
        className="absolute inset-x-0 top-0 h-[3px]"
        style={{
          backgroundImage: "radial-gradient(circle, var(--paper-line) 1px, transparent 1.2px)",
          backgroundSize: "6px 3px",
        }}
      />

      <div className="mt-1 flex items-start justify-between font-mono text-[12.5px]">
        <div>
          <p className="font-semibold">{order.order_id}</p>
          <p className="text-paper-muted">{formatAge(ageMinutes)}</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className="rounded-[5px] bg-ai-soft px-1.5 py-0.5 text-[10px] text-ai">via AI agent</span>
          {isLate && (
            <span className="rounded-[5px] bg-need-soft px-1.5 py-0.5 text-[10px] text-need">
              Late by {lateBy}m
            </span>
          )}
        </div>
      </div>

      <div className="mt-2 border-t border-dashed border-paper-line pt-2 font-mono text-[12.5px]">
        <p>
          {order.customer_name ?? "Customer"} · {order.delivery_address}
        </p>
        <p className="text-paper-muted">{order.payment_method.toUpperCase()}</p>
      </div>

      <div className="mt-2 border-t border-dashed border-paper-line pt-2 font-mono text-[12.5px]">
        {order.items.map((item, i) => (
          <div key={i} className="flex justify-between">
            <span>
              {item.quantity}x {item.name}
            </span>
            <span className="tabular-nums">{formatMoney(item.price * item.quantity, currency)}</span>
          </div>
        ))}
        {order.delivery_fee ? (
          <div className="flex justify-between text-paper-muted">
            <span>Delivery</span>
            <span className="tabular-nums">{formatMoney(order.delivery_fee, currency)}</span>
          </div>
        ) : null}
        <div className="mt-1 flex justify-between border-t border-dashed border-paper-line pt-1 font-semibold">
          <span>Total</span>
          <span className="tabular-nums">{formatMoney(order.total_amount, currency)}</span>
        </div>
      </div>

      {onAdvance && (action || !["delivered", "cancelled"].includes(order.status)) && (
        <div className="mt-3 flex items-center gap-2">
          {action && (
            <button
              type="button"
              onClick={() => onAdvance(action.next)}
              className="flex-1 rounded-[4px] bg-paper-ink px-2 py-1.5 font-mono text-[11px] text-paper hover:opacity-90"
            >
              {action.label}
            </button>
          )}
          {!["delivered", "cancelled"].includes(order.status) && (
            <button
              type="button"
              onClick={() => onAdvance("cancelled")}
              className="rounded-[4px] px-2 py-1.5 font-mono text-[11px] text-need hover:bg-need-soft"
            >
              Cancel
            </button>
          )}
        </div>
      )}
    </div>
  )
}
