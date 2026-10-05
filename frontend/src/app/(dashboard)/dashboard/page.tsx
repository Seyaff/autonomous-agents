"use client"

import * as React from "react"
import { toast } from "sonner"

import { KpiStrip } from "@/components/console/kpi-strip"
import { QueuePane } from "@/components/console/queue-pane"
import { ThreadPane } from "@/components/console/thread-pane"
import { RailPane } from "@/components/console/rail-pane"
import { ReplayLunchRushButton } from "@/components/console/replay-button"
import { useQueue } from "@/hooks/console/use-queue"
import { useThread } from "@/hooks/console/use-thread"
import { useRail, type RailOrder } from "@/hooks/console/use-rail"
import { useKpis } from "@/hooks/console/use-kpis"
import { useCurrentTenant } from "@/hooks/tenant/use-current-tenant"
import { USE_MOCKS } from "@/lib/mocks"
import type { OrderStatus } from "@/lib/status"
import { SetupChecklistCard } from "@/components/setup/setup-checklist-card"

export default function DashboardPage() {
  const [selectedId, setSelectedId] = React.useState<string | null>(null)
  const [justPrintedId, setJustPrintedId] = React.useState<string | null>(null)

  // Shows the result of a payment the customer just made, then clears it from the address bar.
  React.useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const result = params.get("payment")
    if (!result) return
    const message = params.get("message")
    if (result === "ok") toast.success("Payment received.")
    else if (result === "pending") toast.message("Payment is still processing. We'll update your account once it's confirmed.")
    else toast.error(message ? `Payment not completed: ${message}` : "Payment not completed.")
    window.history.replaceState(null, "", window.location.pathname)
  }, [])

  const { data: tenant } = useCurrentTenant()
  const currency = tenant?.currency ?? "USD"

  const queue = useQueue()
  const rail = useRail()
  const kpis = useKpis(queue.groups.needs_you.length)

  // Nothing explicitly picked yet → derive a default (first conversation
  // that needs attention) purely from data, during render. Avoids writing
  // to state from an effect just to mirror data that's already available.
  const autoSelectId =
    queue.groups.needs_you[0]?.conversation_id ??
    queue.groups.agent_handling[0]?.conversation_id ??
    queue.groups.resolved[0]?.conversation_id ??
    null
  const effectiveSelectedId = selectedId ?? autoSelectId

  const thread = useThread(effectiveSelectedId)
  const selectedConversation = effectiveSelectedId ? queue.byId.get(effectiveSelectedId) ?? null : null

  // Mark the open conversation read once its unread count is visible.
  React.useEffect(() => {
    if (selectedConversation && selectedConversation.unread_count > 0) {
      thread.markRead()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveSelectedId, selectedConversation?.unread_count])

  function handleAdvanceOrder(order: RailOrder, next: OrderStatus) {
    rail.advance(order, next)
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <SetupChecklistCard />
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-border bg-card px-4 py-2">
        <KpiStrip kpis={kpis.kpis} currency={currency} />
        {USE_MOCKS && (
          <ReplayLunchRushButton
            onSelectConversation={(id) => {
              setSelectedId(id)
              setJustPrintedId("ORD-7F3A")
            }}
          />
        )}
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden lg:flex-row">
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden md:flex-row">
          <QueuePane
            groups={queue.groups}
            isLoading={queue.isLoading}
            selectedId={effectiveSelectedId}
            onSelect={setSelectedId}
          />
          <ThreadPane
            conversation={selectedConversation}
            messages={thread.messages}
            isLoading={thread.isLoading}
            isSending={thread.isSending}
            onSend={thread.send}
            onToggleTakeover={() =>
              selectedConversation && thread.toggleTakeover(selectedConversation.takeoverByOwner)
            }
            onResolveEscalation={thread.resolveEscalation}
          />
        </div>
        <RailPane
          orders={rail.orders}
          currency={currency}
          isLoading={rail.isLoading}
          onAdvance={handleAdvanceOrder}
          justPrintedId={justPrintedId}
        />
      </div>
    </div>
  )
}
