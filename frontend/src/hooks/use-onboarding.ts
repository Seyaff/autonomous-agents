import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { TenantIdentity, MenuItem } from "@/types";

export function useOnboardingStatus(tenantId?: string) {
  return useQuery({
    queryKey: ["onboarding", tenantId],
    queryFn: () => api.onboarding.getStatus(tenantId!),
    enabled: !!tenantId,
  });
}

export function useStartOnboarding() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; currency?: string }) =>
      api.onboarding.start(data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["onboarding", data.tenant_id] });
    },
  });
}

export function useUpdateIdentity(tenantId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (identity: Partial<TenantIdentity>) =>
      api.onboarding.updateIdentity(tenantId, identity),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["onboarding", tenantId] });
    },
  });
}

export function useUpdateMenu(tenantId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (items: MenuItem[]) =>
      api.onboarding.updateMenu(tenantId, items),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["onboarding", tenantId] });
    },
  });
}

export function useConnectWhatsApp(tenantId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      code?: string;
      phone_number_id?: string;
      waba_id?: string;
      access_token?: string;
    }) => api.onboarding.connectWhatsApp(tenantId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["onboarding", tenantId] });
    },
  });
}

export function useSendKitchenTestSlip(tenantId: string) {
  return useMutation({
    mutationFn: (kitchenPhone: string) =>
      api.onboarding.sendTestKitchenSlip(tenantId, kitchenPhone),
  });
}

export function useCompleteOnboarding(tenantId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.onboarding.complete(tenantId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["onboarding", tenantId] });
    },
  });
}
