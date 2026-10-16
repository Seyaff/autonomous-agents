"use client"

import { AgentStateIndicator } from "@/components/dashboard/agent-state-indicator"
import { AlertsBell } from "@/components/dashboard/alerts-bell"
import { PlanUsageMeter } from "@/components/dashboard/plan-usage-meter"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { useUnreadTotal } from "@/hooks/inbox/use-unread-total"
import { AssistantLauncher } from "@/components/assistant/assistant-panel"
import { useAuth } from "@/components/providers/auth-provider"
import { USE_MOCKS } from "@/lib/mocks"

export function DashboardTopbar() {
  const unread = useUnreadTotal()
  const { isFounder, activeTenantId } = useAuth()

  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-card px-3">
      <div className="flex items-center gap-2">
        <SidebarTrigger />
        {unread > 0 && (
          <span className="rounded-full bg-new-soft px-2 py-0.5 font-mono text-[11px] text-new">
            {unread} unread
          </span>
        )}
      </div>
      <div className="flex items-center gap-4">
        {!USE_MOCKS && !isFounder && !!activeTenantId && <AssistantLauncher />}
        <AlertsBell />
        <AgentStateIndicator />
        <PlanUsageMeter />
      </div>
    </header>
  )
}
