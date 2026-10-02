"use client"

import { useQuery, type QueryClient } from "@tanstack/react-query"
import { MOCK_CONVERSATIONS, type MockConversation } from "@/lib/mock/conversations"
import { useConversations } from "@/hooks/inbox/use-conversations"
import { USE_MOCKS } from "@/lib/mocks"
import type { Conversation } from "@/services/inbox/inbox.service"

const MOCK_QUEUE_KEY = ["mock", "conversations"] as const

export function useMockQueueData() {
  // No `enabled` gate: this is pure in-memory data, not a network call, so
  // there's no cost to always running it — and gating it on USE_MOCKS only
  // introduced a spurious "disabled -> isLoading:false, data:undefined"
  // state that could trip a premature notFound() in the thread page.
  return useQuery({
    queryKey: MOCK_QUEUE_KEY,
    queryFn: async () => MOCK_CONVERSATIONS,
    staleTime: Infinity,
  })
}

export function patchMockConversation(
  queryClient: QueryClient,
  conversationId: string,
  patch: Partial<MockConversation>
) {
  queryClient.setQueryData<MockConversation[]>(MOCK_QUEUE_KEY, (old) =>
    (old ?? []).map((c) => (c.conversation_id === conversationId ? { ...c, ...patch } : c))
  )
}

/** Shared real→mock-shape mapping, used by both the queue (list) and the
 * thread (single-conversation fetch) so a conversation reached by direct
 * link looks identical to one reached via the list. */
export function toQueueConversation(c: Conversation): MockConversation {
  return {
    ...c,
    // TODO(backend): no escalation/takeover flag exists yet (owner
    // roadmap #1) — this approximates "needs you" from unread count until
    // that ships.
    group:
      c.status === "closed" || c.status === "archived"
        ? "resolved"
        : c.unread_count > 0
          ? "needs_you"
          : "agent_handling",
    escalated: false,
    takeoverByOwner: false,
    isAgentTyping: false,
  }
}

function filterMockBySearch(conversations: MockConversation[], search?: string) {
  if (!search) return conversations
  const q = search.toLowerCase()
  return conversations.filter(
    (c) => c.customer_name.toLowerCase().includes(q) || c.customer_phone.toLowerCase().includes(q)
  )
}

export interface QueueGroups {
  needs_you: MockConversation[]
  agent_handling: MockConversation[]
  resolved: MockConversation[]
}

function groupConversations(conversations: MockConversation[]): QueueGroups {
  const groups: QueueGroups = { needs_you: [], agent_handling: [], resolved: [] }
  for (const c of conversations) {
    groups[c.group].push(c)
  }
  return groups
}

export function useQueue(search?: string) {
  const mock = useMockQueueData()
  const real = useConversations(search ? { search } : undefined, { enabled: !USE_MOCKS })

  const conversations: MockConversation[] = USE_MOCKS
    ? filterMockBySearch(mock.data ?? [], search)
    : (real.data?.conversations ?? []).map(toQueueConversation)

  const groups = groupConversations(conversations)
  const byId = new Map(conversations.map((c) => [c.conversation_id, c]))

  return {
    isLoading: USE_MOCKS ? mock.isLoading : real.isLoading,
    groups,
    byId,
  }
}
