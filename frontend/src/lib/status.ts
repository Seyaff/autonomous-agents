/**
 * One consistent status→badge mapping, used anywhere a status pill is
 * rendered (orders, conversations, messages). Keeps colors to the
 * semantic tokens in globals.css instead of each component picking its
 * own raw Tailwind swatch.
 */

export type StatusTone = "neutral" | "info" | "warning" | "success" | "danger"

const toneClassName: Record<StatusTone, string> = {
  neutral: "bg-(--status-neutral-bg) text-(--status-neutral-fg)",
  info: "bg-(--status-info-bg) text-(--status-info-fg)",
  warning: "bg-(--status-warning-bg) text-(--status-warning-fg)",
  success: "bg-(--status-success-bg) text-(--status-success-fg)",
  danger: "bg-(--status-danger-bg) text-(--status-danger-fg)",
}

export function statusBadgeClassName(tone: StatusTone): string {
  return `${toneClassName[tone]} border-transparent`
}

// Order status, as returned by the backend (app/api/v1/endpoints/orders.py).
export type OrderStatus =
  | "pending"
  | "accepted"
  | "preparing"
  | "out_for_delivery"
  | "delivered"
  | "cancelled"

export const ORDER_STATUS_CONFIG: Record<
  OrderStatus,
  { label: string; tone: StatusTone }
> = {
  pending: { label: "Pending", tone: "warning" },
  accepted: { label: "Accepted", tone: "info" },
  preparing: { label: "Preparing", tone: "info" },
  out_for_delivery: { label: "Out for delivery", tone: "info" },
  delivered: { label: "Delivered", tone: "success" },
  cancelled: { label: "Cancelled", tone: "danger" },
}

export function orderStatusBadge(status: string) {
  const config = ORDER_STATUS_CONFIG[status as OrderStatus] ?? {
    label: status,
    tone: "neutral" as StatusTone,
  }
  return { label: config.label, className: statusBadgeClassName(config.tone) }
}

// Message delivery status, as returned by the inbox endpoints.
export type MessageStatus =
  | "received"
  | "sending"
  | "sent"
  | "delivered"
  | "read"
  | "failed"

export const MESSAGE_STATUS_CONFIG: Record<
  MessageStatus,
  { label: string; tone: StatusTone }
> = {
  received: { label: "Received", tone: "neutral" },
  sending: { label: "Sending", tone: "warning" },
  sent: { label: "Sent", tone: "info" },
  delivered: { label: "Delivered", tone: "success" },
  read: { label: "Read", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
}
