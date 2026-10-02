import type { Order } from "@/services/orders/orders.service"
import { MOCK_TENANT_ID } from "@/lib/mock/conversations"

export interface MockOrder extends Order {
  delivery_fee: number
  source: "ai_agent" | "owner"
  eta_minutes: number
}

const minutesAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString()

export const MOCK_ORDERS: MockOrder[] = [
  {
    order_id: "ORD-5F12",
    tenant_id: MOCK_TENANT_ID,
    customer_phone: "+92 300 9998888",
    customer_name: "Sana Malik",
    delivery_address: "Pickup",
    items: [{ name: "Chicken Karahi", quantity: 1, price: 1450 }],
    total_amount: 1450,
    payment_method: "cod",
    customer_notes: null,
    status: "delivered",
    created_at: minutesAgo(98),
    updated_at: minutesAgo(80),
    delivery_fee: 0,
    source: "ai_agent",
    eta_minutes: 20,
  },
  {
    order_id: "ORD-3C88",
    tenant_id: MOCK_TENANT_ID,
    customer_phone: "+92 300 1112222",
    customer_name: "Bilal Ahmed",
    delivery_address: "House 12, Gulberg III",
    items: [{ name: "Chicken Biryani", quantity: 2, price: 650 }],
    total_amount: 1450,
    payment_method: "cod",
    customer_notes: null,
    status: "out_for_delivery",
    created_at: minutesAgo(45),
    updated_at: minutesAgo(10),
    delivery_fee: 150,
    source: "ai_agent",
    eta_minutes: 35,
  },
  {
    order_id: "ORD-9K41",
    tenant_id: MOCK_TENANT_ID,
    customer_phone: "+92 333 7778899",
    customer_name: "Owais Tariq",
    delivery_address: "DHA Phase 5",
    items: [{ name: "Beef Karahi", quantity: 1, price: 1900 }],
    total_amount: 2050,
    payment_method: "card",
    customer_notes: null,
    status: "preparing",
    created_at: minutesAgo(18),
    updated_at: minutesAgo(5),
    delivery_fee: 150,
    source: "ai_agent",
    eta_minutes: 30,
  },
  {
    order_id: "ORD-1Q77",
    tenant_id: MOCK_TENANT_ID,
    customer_phone: "+92 301 4445566",
    customer_name: "Zara Niazi",
    delivery_address: "Gulberg III, Block B",
    items: [{ name: "Mutton Pulao", quantity: 2, price: 850 }],
    total_amount: 1850,
    payment_method: "cod",
    customer_notes: "Less spicy",
    status: "pending",
    created_at: minutesAgo(3),
    updated_at: minutesAgo(3),
    delivery_fee: 150,
    source: "ai_agent",
    eta_minutes: 40,
  },
]
