import API from "@/lib/axios-client"
import type { OrderStatus } from "@/lib/status"

export interface OrderItem {
  name: string
  quantity: number
  price: number
  notes?: string | null
}

export interface Order {
  order_id: string
  tenant_id: string
  customer_phone: string
  customer_name?: string | null
  delivery_address: string
  items: OrderItem[]
  total_amount: number
  payment_method: string
  customer_notes?: string | null
  status: OrderStatus
  created_at: string
  updated_at: string
}

export interface OrdersListResponse {
  status: string
  total: number
  orders: Order[]
}

export interface OrderStatsSummary {
  total_orders: number
  total_revenue: number
  pending_orders: number
  completed_orders: number
  cancelled_orders: number
}

export interface ListOrdersParams {
  status?: string
  limit?: number
  skip?: number
}

export const listOrders = async (
  params?: ListOrdersParams
): Promise<OrdersListResponse> => {
  const res = await API.get("/orders", { params })
  return res.data
}

export const getOrderStatsSummary = async (): Promise<OrderStatsSummary> => {
  const res = await API.get("/orders/stats/summary")
  return res.data
}

export const updateOrderStatus = async (
  orderId: string,
  status: OrderStatus,
  notes?: string
) => {
  const res = await API.patch(`/orders/${orderId}`, { status, notes })
  return res.data
}
