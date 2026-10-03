"use client"

import * as React from "react"
import { notFound } from "next/navigation"

import { ThreadPane } from "@/components/console/thread-pane"
import { useThread } from "@/hooks/console/use-thread"

export default function InboxConversationPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  // Next.js does not decode dynamic-segment params itself — a conversation
  // id containing `+` (from a phone number) arrives here still encoded as
  // `%2B` from the sidebar's encodeURIComponent(), so it must be decoded
  // back before it can match anything.
  const { id: rawId } = React.use(params)
  const id = decodeURIComponent(rawId)
  const thread = useThread(id)

  // React Query only starts fetching inside an effect, and no effects run
  // during the server render — so on a fresh request `isLoading` reads
  // false (the fetch never started) while data is still undefined. Calling
  // notFound() before confirming we're mounted client-side would 404 every
  // direct link/reload before the real fetch ever got a chance to run.
  const [mounted, setMounted] = React.useState(false)
  React.useEffect(() => {
    // Detecting "client has hydrated" has no purer implementation than
    // this — same pattern next-themes uses internally for the same reason.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true)
  }, [])

  React.useEffect(() => {
    if (thread.conversation && thread.conversation.unread_count > 0) {
      thread.markRead()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, thread.conversation?.unread_count])

  if (mounted && !thread.isLoading && !thread.conversation) {
    notFound()
  }

  return (
    <ThreadPane
      conversation={thread.conversation}
      messages={thread.messages}
      isLoading={!mounted || thread.isLoading}
      isSending={thread.isSending}
      onSend={thread.send}
      onToggleTakeover={() => thread.conversation && thread.toggleTakeover(thread.conversation.takeoverByOwner)}
      onResolveEscalation={thread.resolveEscalation}
    />
  )
}
