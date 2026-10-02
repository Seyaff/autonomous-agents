"use client"

import { useConversations } from "@/hooks/inbox/use-conversations"

/** Cheap read of the sidebar's unread badge — piggybacks on the same
 * conversations list query (React Query dedupes identical keys), just
 * reading the `unread_total` every list response already carries. */
export const useUnreadTotal = () => {
  const { data } = useConversations({ limit: 1 })
  return data?.unread_total ?? 0
}
