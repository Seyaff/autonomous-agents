"use client"

import { useQuery } from "@tanstack/react-query"
import { listConversations, type ListConversationsParams } from "@/services/inbox/inbox.service"

export const useConversations = (params?: ListConversationsParams) => {
  return useQuery({
    queryKey: ["inbox", "conversations", params],
    queryFn: () => listConversations(params),
    // The websocket keeps this live; this is just a backstop in case a
    // tab misses an event (e.g. briefly disconnected).
    refetchInterval: 30_000,
  })
}
