"use client"

import { useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { MOCK_ORDERS, type MockOrder } from "@/lib/mock/orders"
import { useOrders } from "@/hooks/orders/use-orders"
import { useUpdateOrderStatus } from "@/hooks/orders/use-update-order-status"
import { USE_MOCKS } from "@/lib/mocks"
import type { Order } from "@/services/orders/orders.service"
import type { OrderStatus } from "@/lib/status"

export type RailOrder = Order & Partial<Pick<MockOrder, "delivery_fee" | "source" | "eta_minutes">>

const MOCK_ORDERS_KEY = ["mock", "orders"] as const

const STATUS_PHRASE: Partial<Record<OrderStatus, string>> = {
  accepted: "was accepted",
  preparing: "moved to the kitchen",
  out_for_delivery: "is on the way",
  delivered: "was delivered",
  cancelled: "was cancelled",
}

export function useMockOrdersData() {
  // No `enabled` gate — see use-queue.ts's useMockQueueData for why.
  return useQuery({
    queryKey: MOCK_ORDERS_KEY,
    queryFn: async () => MOCK_ORDERS,
    staleTime: Infinity,
  })
}

export function patchMockOrder(queryClient: QueryClient, orderId: string, patch: Partial<MockOrder>) {
  queryClient.setQueryData<MockOrder[]>(MOCK_ORDERS_KEY, (old) =>
    (old ?? []).map((o) => (o.order_id === orderId ? { ...o, ...patch } : o))
  )
}

export function addMockOrder(queryClient: QueryClient, order: MockOrder) {
  queryClient.setQueryData<MockOrder[]>(MOCK_ORDERS_KEY, (old) => [order, ...(old ?? [])])
}

export function useRail() {
  const queryClient = useQueryClient()
  const mock = useMockOrdersData()
  const real = useOrders(USE_MOCKS ? undefined : { limit: 100 }, { enabled: !USE_MOCKS })
  const updateStatus = useUpdateOrderStatus()

  const orders: RailOrder[] = USE_MOCKS ? mock.data ?? [] : real.data?.orders ?? []

  function advance(order: RailOrder, nextStatus: OrderStatus) {
    if (USE_MOCKS) {
      patchMockOrder(queryClient, order.order_id, { status: nextStatus, updated_at: new Date().toISOString() })
      const phrase = STATUS_PHRASE[nextStatus]
      if (phrase) {
        toast(`${order.order_id} ${phrase}. ${order.customer_name ?? "The customer"} got a WhatsApp update.`)
      }
      return
    }

    updateStatus.mutate(
      { orderId: order.order_id, status: nextStatus },
      {
        onSuccess: (data: { customer_notified?: boolean }) => {
          const phrase = STATUS_PHRASE[nextStatus]
          if (!phrase) return
          toast(
            data.customer_notified
              ? `${order.order_id} ${phrase}. The customer got a WhatsApp update.`
              : `${order.order_id} ${phrase}. The customer was not messaged (outside the 24-hour WhatsApp window).`
          )
        },
        onError: (err: unknown) => {
          const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
          toast.error(detail ?? "Could not update the order.")
        },
      }
    )
  }

  return {
    isLoading: USE_MOCKS ? mock.isLoading : real.isLoading,
    orders,
    advance,
  }
}
