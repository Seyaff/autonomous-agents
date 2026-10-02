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

/** Minimal shape the chrome (tenant switcher, agent state indicator) needs,
 * shared by both the real tenant and the mock ones — the backend has no
 * "branch" concept, so `branch_name` only ever comes from mock data. */
export interface TenantSummary {
  tenant_id: string
  business_name: string
  branch_name?: string
  currency: string
  whatsapp_connected?: boolean
  phone_number_id?: string | null
  display_phone_number?: string | null
}

export function toTenantSummary(tenant: Tenant): TenantSummary {
  return {
    tenant_id: tenant.tenant_id,
    business_name: tenant.business_name,
    currency: tenant.currency,
    whatsapp_connected: tenant.whatsapp_connected,
    phone_number_id: tenant.phone_number_id,
    display_phone_number: tenant.display_phone_number,
  }
}
