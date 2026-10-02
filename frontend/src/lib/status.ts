/**
 * Canonical status vocabulary — DESIGN.md §5. These are the only values
 * the backend ever sends; never invent new ones in the frontend.
 */

import type { ChipTone } from "@/components/console/status-chip"

// Order status, as returned by the backend (app/api/v1/endpoints/orders.py).
export type OrderStatus =
  | "pending"
  | "accepted"
  | "preparing"
  | "out_for_delivery"
  | "delivered"
  | "cancelled"

export const ORDER_STATUS_DISPLAY: Record<OrderStatus, { label: string; tone: ChipTone }> = {
  pending: { label: "New", tone: "new" },
  accepted: { label: "Accepted", tone: "new" },
  preparing: { label: "In the kitchen", tone: "neutral" },
  out_for_delivery: { label: "On the way", tone: "neutral" },
  delivered: { label: "Delivered", tone: "ok" },
  cancelled: { label: "Cancelled", tone: "need" },
}

// Message delivery status, as returned by the inbox endpoints.
export type MessageStatus =
  | "received"
  | "sending"
  | "sent"
  | "delivered"
  | "read"
  | "failed"
