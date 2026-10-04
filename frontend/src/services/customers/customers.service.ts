import API from "@/lib/axios-client"

export interface CustomerRow {
  customer_phone: string
  name: string | null
  total_orders: number
  total_spent: number
  currency: string | null
  last_order_at: string | null
}

export interface CustomerFact {
  kind: string
  key: string
  value: string
  updated_at: string
}

export interface CustomerDetail {
  customer: {
    customer_phone: string
    name: string | null
    total_orders: number
    delivered_orders: number
    cancelled_orders: number
    total_spent: number
    first_order_at: string | null
    last_order_at: string | null
    favourites: { name: string; quantity: number }[]
    last_order: { order_id: string; status: string; total_amount: number; currency: string } | null
    facts: CustomerFact[]
  }
  recent_orders: {
    order_id: string
    status: string
    total_amount: number
    currency: string
    created_at: string
    items: { name: string; quantity: number }[]
  }[]
}

export const listCustomers = async (search: string): Promise<{ total: number; customers: CustomerRow[] }> => {
  const res = await API.get("/customers", { params: { search: search || undefined, limit: 100 } })
  return res.data
}

export const getCustomer = async (phone: string): Promise<CustomerDetail> => {
  const res = await API.get(`/customers/${encodeURIComponent(phone)}`)
  return res.data
}

export interface CustomerFactRow {
  id: string
  kind: string
  key: string
  value: string
}

export const listCustomerFacts = async (phone: string): Promise<CustomerFactRow[]> => {
  const res = await API.get(`/customers/${encodeURIComponent(phone)}/facts`)
  return res.data.facts
}

export const correctCustomerFact = async (phone: string, id: string, value: string) => {
  const res = await API.patch(`/customers/${encodeURIComponent(phone)}/facts/${id}`, { value })
  return res.data
}

export const forgetCustomerFact = async (phone: string, id: string) => {
  const res = await API.delete(`/customers/${encodeURIComponent(phone)}/facts/${id}`)
  return res.data
}
