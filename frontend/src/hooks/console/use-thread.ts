"use client"

import { useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { MOCK_TENANT_ID } from "@/lib/mock/conversations"
import { MOCK_MESSAGES, type MockMessage } from "@/lib/mock/messages"
import { useConversation } from "@/hooks/inbox/use-conversation"
import { useSendMessage } from "@/hooks/inbox/use-send-message"
import { useMarkConversationRead } from "@/hooks/inbox/use-mark-read"
import { patchMockConversation, toQueueConversation, useMockQueueData } from "@/hooks/console/use-queue"
import { USE_MOCKS } from "@/lib/mocks"
import type { MockConversation } from "@/lib/mock/conversations"

function mockMessagesKey(conversationId: string) {
  return ["mock", "messages", conversationId] as const
}

export function useMockMessages(conversationId: string | null) {
  // Gated only on having an id (not on USE_MOCKS — see use-queue.ts's
  // useMockQueueData for why that gate caused a premature notFound()).
  return useQuery({
    queryKey: mockMessagesKey(conversationId ?? ""),
    queryFn: async () => MOCK_MESSAGES[conversationId ?? ""] ?? [],
    enabled: !!conversationId,
    staleTime: Infinity,
  })
}

export function appendMockMessage(queryClient: QueryClient, conversationId: string, message: MockMessage) {
  queryClient.setQueryData<MockMessage[]>(mockMessagesKey(conversationId), (old) => [...(old ?? []), message])
}

export function useThread(conversationId: string | null) {
  const queryClient = useQueryClient()
  const mockQueue = useMockQueueData()
  const mockMessages = useMockMessages(conversationId)
  const real = useConversation(USE_MOCKS ? null : conversationId)
  const realSend = useSendMessage(conversationId ?? "")
  const realMarkRead = useMarkConversationRead()

  const messages: MockMessage[] = USE_MOCKS ? mockMessages.data ?? [] : real.data?.messages ?? []

  // Resolved independently of the list query — so a conversation reached by
  // direct link (e.g. /dashboard/inbox/{id}) still loads correctly even if
  // it wouldn't be on the first page of the list fetch.
  const conversation: MockConversation | null = USE_MOCKS
    ? (mockQueue.data ?? []).find((c) => c.conversation_id === conversationId) ?? null
    : real.data?.conversation
      ? toQueueConversation(real.data.conversation)
      : null

  function send(content: string) {
    if (!conversationId) return
    if (USE_MOCKS) {
      appendMockMessage(queryClient, conversationId, {
        message_id: `mock_msg_${Date.now()}`,
        wamid: null,
        conversation_id: conversationId,
        tenant_id: MOCK_TENANT_ID,
        sender: "human",
        sender_phone: null,
        content,
        type: "text",
        status: "sent",
        created_at: new Date().toISOString(),
        delivered_at: null,
        read_at: null,
      })
      patchMockConversation(queryClient, conversationId, {
        takeoverByOwner: true,
        last_message: { content, sender: "human", timestamp: new Date().toISOString(), type: "text" },
        last_activity_at: new Date().toISOString(),
      })
      return
    }
    realSend.mutate(content)
  }

  function markRead() {
    if (!conversationId) return
    if (USE_MOCKS) {
      patchMockConversation(queryClient, conversationId, { unread_count: 0 })
      return
    }
    realMarkRead.mutate(conversationId)
  }

  function toggleTakeover(current: boolean) {
    if (!conversationId) return
    if (!USE_MOCKS) {
      // TODO(backend): takeover isn't wired to any API yet (owner roadmap #1).
      toast.info("Takeover isn't wired to the backend yet.")
      return
    }
    patchMockConversation(queryClient, conversationId, { takeoverByOwner: !current })
  }

  return {
    // In mock mode, `conversation` depends on mockQueue settling too — if
    // only mockMessages.isLoading were checked here, a caller could see
    // isLoading:false with conversation still null for one tick and
    // wrongly conclude the conversation doesn't exist (this is what caused
    // the inbox 404 bug).
    isLoading: USE_MOCKS ? mockQueue.isLoading || mockMessages.isLoading : real.isLoading,
    conversation,
    messages,
    send,
    markRead,
    toggleTakeover,
    isSending: USE_MOCKS ? false : realSend.isPending,
  }
}
