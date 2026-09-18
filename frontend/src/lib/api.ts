import { apiClient } from "@/lib/axios";
import type {
  OnboardingStatusResponse,
  TenantIdentity,
  MenuItem,
  LiveOrder,
  OrderStatus,
} from "@/types";

export const api = {
  // Onboarding API Endpoints
  onboarding: {
    start: (data: { name: string; currency?: string }): Promise<{ tenant_id: string; slug: string }> => {
      return apiClient.post("/onboarding/start", data);
    },

    getStatus: (tenantId: string): Promise<OnboardingStatusResponse> => {
      return apiClient.get(`/onboarding/${tenantId}/status`);
    },

    updateIdentity: (
      tenantId: string,
      identity: Partial<TenantIdentity>
    ): Promise<OnboardingStatusResponse> => {
      return apiClient.patch(`/onboarding/${tenantId}/identity`, identity);
    },

    updateMenu: (
      tenantId: string,
      items: MenuItem[]
    ): Promise<{ count: number; items: MenuItem[] }> => {
      return apiClient.post(`/onboarding/${tenantId}/menu`, { items });
    },

    connectWhatsApp: (
      tenantId: string,
      payload: { code?: string; phone_number_id?: string; waba_id?: string; access_token?: string }
    ): Promise<{ success: boolean; phone_number: string }> => {
      return apiClient.post(`/onboarding/${tenantId}/whatsapp`, payload);
    },

    sendTestKitchenSlip: (
      tenantId: string,
      kitchenPhone: string
    ): Promise<{ success: boolean; message: string }> => {
      return apiClient.post(`/onboarding/${tenantId}/test-kitchen`, { kitchen_phone: kitchenPhone });
    },

    complete: (tenantId: string): Promise<{ success: boolean; whatsapp_link: string }> => {
      return apiClient.post(`/onboarding/${tenantId}/complete`);
    },
  },

  // Orders API Endpoints
  orders: {
    list: (tenantId: string): Promise<LiveOrder[]> => {
      return apiClient.get(`/orders?tenant_id=${tenantId}`);
    },

    updateStatus: (
      orderId: string,
      status: OrderStatus
    ): Promise<{ success: boolean; order_id: string; status: OrderStatus }> => {
      return apiClient.patch(`/orders/${orderId}/status`, { status });
    },
  },

  // Marketing API Endpoints
  marketing: {
    getStats: (tenantId: string) => {
      return apiClient.get(`/marketing/stats?tenant_id=${tenantId}`);
    },
    triggerWinBack: (tenantId: string) => {
      return apiClient.post(`/marketing/trigger-winback`, { tenant_id: tenantId });
    },
  },
};
