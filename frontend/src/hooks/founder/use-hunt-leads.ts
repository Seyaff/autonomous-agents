"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { huntLeads } from "@/services/founder/founder.service"

export const useHuntLeads = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ query, maxLeads }: { query: string; maxLeads: number }) =>
      huntLeads(query, maxLeads),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["founder", "campaigns"] })
    },
  })
}
