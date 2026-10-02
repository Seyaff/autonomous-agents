"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { sendMessage } from "@/services/inbox/inbox.service"

export const useSendMessage = (conversationId: string) => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (content: string) => sendMessage(conversationId, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inbox", "conversation", conversationId] })
      queryClient.invalidateQueries({ queryKey: ["inbox", "conversations"] })
    },
  })
}
