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

/** Full restaurant record for the settings page (the chrome only needs TenantSummary). */
export interface TenantSettings {
  tenant_id: string
  business_name: string
  business_phone?: string | null
  address?: string | null
  currency: string
  timezone: string
  whatsapp_connected: boolean
  whatsapp_status?: "connected" | "disconnected" | "error"
  whatsapp_last_error?: string | null
  verified_name?: string | null
  display_phone_number?: string | null
  agent_enabled: boolean
  delivery_settings: {
    flat_delivery_fee?: number
    avg_prep_time_minutes?: number
  }
}

export const getTenantSettings = async (): Promise<TenantSettings> => {
  const res = await API.get("/tenant/current")
  return res.data
}

export interface TenantSettingsUpdate {
  business_name?: string
  business_phone?: string
  address?: string
  currency?: string
  timezone?: string
  flat_delivery_fee?: number
  avg_prep_time_minutes?: number
}

export const updateTenantSettings = async (payload: TenantSettingsUpdate) => {
  const res = await API.patch("/tenant/current", payload)
  return res.data
}

export const setAgentEnabled = async (enabled: boolean) => {
  const res = await API.patch("/tenant/current/agent", { enabled })
  return res.data as { agent_enabled: boolean }
}
