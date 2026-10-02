"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { markConversationRead } from "@/services/inbox/inbox.service"

export const useMarkConversationRead = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (conversationId: string) => markConversationRead(conversationId),
    onSuccess: (_data, conversationId) => {
      queryClient.invalidateQueries({ queryKey: ["inbox", "conversation", conversationId] })
      queryClient.invalidateQueries({ queryKey: ["inbox", "conversations"] })
    },
  })
}
