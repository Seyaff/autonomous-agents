"use client"

import { useQuery } from "@tanstack/react-query"
import { getConversation } from "@/services/inbox/inbox.service"

export const useConversation = (conversationId: string | null) => {
  return useQuery({
    queryKey: ["inbox", "conversation", conversationId],
    queryFn: () => getConversation(conversationId as string),
    enabled: !!conversationId,
  })
}
