import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { OrderStatus } from "@/types";

export function useOrders(tenantId?: string) {
  return useQuery({
    queryKey: ["orders", tenantId],
    queryFn: () => api.orders.list(tenantId!),
    enabled: !!tenantId,
    refetchInterval: 5000, // Poll every 5 seconds as fallback to WebSocket
  });
}

export function useUpdateOrderStatus(tenantId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ orderId, status }: { orderId: string; status: OrderStatus }) =>
      api.orders.updateStatus(orderId, status),
    onSuccess: () => {
      if (tenantId) {
        queryClient.invalidateQueries({ queryKey: ["orders", tenantId] });
      }
    },
  });
}
