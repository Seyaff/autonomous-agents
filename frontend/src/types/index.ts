export type OnboardingStep =
  | "DRAFT"
  | "IDENTITY_SAVED"
  | "MENU_INGESTED"
  | "WHATSAPP_CONNECTED"
  | "KITCHEN_VERIFIED"
  | "ACTIVE";

export interface TenantIdentity {
  name: string;
  tagline?: string;
  cuisine: string;
  city: string;
  address: string;
  opening_hours: string;
  currency: string;
  kitchen_phone: string;
}

export interface OnboardingStatusResponse {
  tenant_id: string;
  slug: string;
  current_step: OnboardingStep;
  progress_percentage: number;
  identity: Partial<TenantIdentity>;
  whatsapp_connected: boolean;
  kitchen_verified: boolean;
  whatsapp_link?: string;
}

export interface MenuItem {
  id?: string;
  name: string;
  category: string;
  price: number;
  is_available: boolean;
  description?: string;
}

export type OrderStatus =
  | "pending"
  | "confirmed"
  | "preparing"
  | "out_for_delivery"
  | "delivered"
  | "cancelled";

export interface OrderItem {
  id: string;
  name: string;
  quantity: number;
  unit_price: number;
  total_price: number;
  notes?: string;
}

export interface LiveOrder {
  id: string;
  order_number: string;
  customer_phone: string;
  customer_name?: string;
  delivery_address: string;
  delivery_type: "delivery" | "dine_in" | "takeaway";
  status: OrderStatus;
  total_amount: number;
  payment_method: string;
  payment_status: string;
  items: OrderItem[];
  created_at: string;
  updated_at: string;
  elapsed_minutes?: number;
}
