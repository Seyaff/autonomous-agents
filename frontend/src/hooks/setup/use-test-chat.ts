"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { getTestTranscript, resetTestChat, sendTestMessage } from "@/services/setup/setup.service"

const KEY = ["agent", "test"] as const

export function useTestChat() {
  const queryClient = useQueryClient()
  const transcript = useQuery({ queryKey: KEY, queryFn: getTestTranscript })

  const send = useMutation({
    mutationFn: (message: string) => sendTestMessage(message),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
  })

  const reset = useMutation({
    mutationFn: resetTestChat,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
  })

  return { transcript, send, reset }
}
