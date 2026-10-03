"use client"

import { AgentStateIndicator } from "@/components/dashboard/agent-state-indicator"
import { AlertsBell } from "@/components/dashboard/alerts-bell"
import { PlanUsageMeter } from "@/components/dashboard/plan-usage-meter"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { useUnreadTotal } from "@/hooks/inbox/use-unread-total"

export function DashboardTopbar() {
  const unread = useUnreadTotal()

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
        <AlertsBell />
        <AgentStateIndicator />
        <PlanUsageMeter />
      </div>
    </header>
  )
}
