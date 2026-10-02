import type { TenantSummary } from "@/services/tenant/tenant.service"

export const MOCK_ACTIVE_TENANT_ID = "daal-dough-gulberg"

export const MOCK_TENANTS: TenantSummary[] = [
  {
    tenant_id: "daal-dough-gulberg",
    business_name: "Daal & Dough",
    branch_name: "Gulberg III",
    currency: "PKR",
    whatsapp_connected: true,
    phone_number_id: "mock-phone-gulberg",
    display_phone_number: "+92 42 3587 1180",
  },
  {
    tenant_id: "daal-dough-dha",
    business_name: "Daal & Dough",
    branch_name: "DHA Phase 5",
    currency: "PKR",
    whatsapp_connected: true,
    phone_number_id: "mock-phone-dha",
    display_phone_number: "+92 42 3719 2254",
  },
  {
    tenant_id: "daal-dough-bahria",
    business_name: "Daal & Dough",
    branch_name: "Bahria Town",
    currency: "PKR",
    whatsapp_connected: false,
    phone_number_id: null,
    display_phone_number: null,
  },
]
