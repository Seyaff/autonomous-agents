import API from "@/lib/axios-client"

export type StaffRole = "waiter" | "reception" | "kitchen"

export interface StaffMember {
  staff_id: string
  name: string
  role: StaffRole
  status: string
  locked: boolean
  removed: boolean
}

export interface RosterEntry {
  staff_id: string
  name: string
  role: StaffRole
  locked: boolean
}

export interface MenuItem {
  name: string
  category: string
  price: number
  sold_out: boolean
}

export interface TableState {
  table_no: number
  status: "free" | "sent" | "ready" | "served" | "bill"
  total: number
  order_ids: string[]
}

export interface OrderLine {
  name: string
  qty: number
  price: number
}

export interface TableOrder {
  order_id: string
  table_no: number
  waiter_name: string
  items: OrderLine[]
  status: "sent" | "served" | "billed" | "paid"
  kitchen_status: "new" | "cooking" | "ready"
  created_at: string
}

// Owner dashboard.
export const listStaff = async () => (await API.get<{ staff: StaffMember[]; table_count: number }>("/tenant/current/staff")).data
export const addStaff = async (body: { name: string; role: StaffRole; pin: string }) =>
  (await API.post<StaffMember>("/tenant/current/staff", body)).data
export const resetStaffPin = async (id: string, pin: string) =>
  (await API.post(`/tenant/current/staff/${id}/reset-pin`, { pin })).data
export const unlockStaff = async (id: string) => (await API.post(`/tenant/current/staff/${id}/unlock`)).data
export const removeStaff = async (id: string) => (await API.post(`/tenant/current/staff/${id}/remove`)).data
export const setTableCount = async (count: number) =>
  (await API.put<{ count: number }>("/tenant/current/dine-tables/count", { count })).data

// The iPad and the kitchen screen.
export const staffRoster = async (restaurant: string) =>
  (await API.get<{ waiters: RosterEntry[] }>("/staff/roster", { params: { restaurant } })).data.waiters
export const staffSignIn = async (restaurant: string, staff_id: string, pin: string) =>
  (await API.post<{ staff: StaffMember }>("/staff/sign-in", { restaurant, staff_id, pin, device: "iPad" })).data.staff
export const staffSignOut = async () => API.post("/staff/sign-out")
export const staffMe = async () => (await API.get<StaffMember>("/staff/me")).data
export const staffMenu = async () => (await API.get<{ items: MenuItem[] }>("/staff/menu")).data.items
export const staffTables = async () => (await API.get<{ tables: TableState[] }>("/staff/tables")).data.tables
export const staffOpenOrders = async () => (await API.get<{ orders: TableOrder[] }>("/staff/orders")).data.orders
export const sendTableOrder = async (table_no: number, items: { name: string; qty: number }[]) =>
  (await API.post<TableOrder>("/staff/orders", { table_no, items })).data
export const markServed = async (order_id: string) => API.post(`/staff/orders/${order_id}/served`)
export const kitchenStep = async (order_id: string, status: "cooking" | "ready") =>
  API.post(`/staff/orders/${order_id}/kitchen`, { status })
export const requestBill = async (table_no: number) =>
  (await API.post<{ total: number }>(`/staff/tables/${table_no}/bill`)).data
export const markPaidCash = async (table_no: number) => API.post(`/staff/tables/${table_no}/paid`)

// The restaurant's iPad code. Shown to the owner, typed once on each iPad.
export const getStaffCode = async () => (await API.get<{ code: string }>("/tenant/current/staff-code")).data.code
export const rotateStaffCode = async () =>
  (await API.post<{ code: string }>("/tenant/current/staff-code/rotate")).data.code
export const linkIpad = async (restaurant: string, code: string) =>
  API.post("/staff/link", { restaurant, code })
