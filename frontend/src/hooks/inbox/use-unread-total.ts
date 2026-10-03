"use client"

import { useConversations } from "@/hooks/inbox/use-conversations"
import { USE_MOCKS } from "@/lib/mocks"
import { useAuth } from "@/components/providers/auth-provider"

// TODO(backend): Step 3 makes the inbox hooks themselves mock-aware
// (full conversation/message data); this hardcoded count goes away then.
const MOCK_UNREAD_TOTAL = 3

/** Cheap read of the sidebar's unread badge — piggybacks on the same
 * conversations list query (React Query dedupes identical keys), just
 * reading the `unread_total` every list response already carries. */
export const useUnreadTotal = () => {
  const { activeTenantId } = useAuth()
  const { data } = useConversations({ limit: 1 }, { enabled: !USE_MOCKS && !!activeTenantId })
  if (USE_MOCKS) return MOCK_UNREAD_TOTAL
  return data?.unread_total ?? 0
}
