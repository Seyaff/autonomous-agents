"use client"

import { useQuery } from "@tanstack/react-query"
import { listOrders, type ListOrdersParams } from "@/services/orders/orders.service"

export const useOrders = (params?: ListOrdersParams) => {
  return useQuery({
    queryKey: ["orders", "list", params],
    queryFn: () => listOrders(params),
  })
}
