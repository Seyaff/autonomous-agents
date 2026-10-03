"use client"

import { useQuery } from "@tanstack/react-query"
import { getMenuItems } from "@/services/setup/setup.service"

export function useMenuItems(enabled = true) {
  return useQuery({
    queryKey: ["tenant", "menu-items"],
    queryFn: getMenuItems,
    enabled,
  })
}
