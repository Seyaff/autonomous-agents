import API from "@/lib/axios-client"

export interface Tenant {
  tenant_id: string
  tenant_slug: string
  business_name: string
  business_phone?: string | null
  address?: string | null
  currency: string
  timezone: string
  whatsapp_connected?: boolean
  phone_number_id?: string | null
  display_phone_number?: string | null
  created_at: string
  updated_at: string
}

export const getCurrentTenant = async (): Promise<Tenant> => {
  const res = await API.get("/tenant/current")
  return res.data
}
