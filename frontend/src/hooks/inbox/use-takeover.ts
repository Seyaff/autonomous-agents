"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import {
  takeOverConversation,
  handBackConversation,
  resolveEscalation,
} from "@/services/inbox/inbox.service"

/** Ownership changes for a conversation. Each one refreshes the queue (so the
 * chat moves to its new group) and the open thread. */
export const useTakeover = (conversationId: string) => {
  const queryClient = useQueryClient()

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["inbox", "conversation", conversationId] })
    queryClient.invalidateQueries({ queryKey: ["inbox", "conversations"] })
  }

  const takeOver = useMutation({
    mutationFn: () => takeOverConversation(conversationId),
    onSuccess: refresh,
  })

  const handBack = useMutation({
    mutationFn: () => handBackConversation(conversationId),
    onSuccess: refresh,
  })

  const resolve = useMutation({
    mutationFn: () => resolveEscalation(conversationId),
    onSuccess: refresh,
  })

  return { takeOver, handBack, resolve }
}
