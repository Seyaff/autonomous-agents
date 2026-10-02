"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { updateOrderStatus } from "@/services/orders/orders.service"
import type { OrderStatus } from "@/lib/status"

export const useUpdateOrderStatus = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      orderId,
      status,
      notes,
    }: {
      orderId: string
      status: OrderStatus
      notes?: string
    }) => updateOrderStatus(orderId, status, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orders"] })
      queryClient.invalidateQueries({ queryKey: ["analytics"] })
    },
  })
}
