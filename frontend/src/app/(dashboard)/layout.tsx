"use client"

import { AppSidebar } from "@/components/sidebar/app-sidebar"
import { DashboardTopbar } from "@/components/dashboard/dashboard-topbar"
import {
  SidebarInset,
  SidebarProvider,
} from "@/components/ui/sidebar"
import { useAuth } from "@/components/providers/auth-provider"
import { useInboxSocket } from "@/hooks/inbox/use-inbox-socket"
import { USE_MOCKS } from "@/lib/mocks"

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const { isAuthenticated, isFounder, activeTenantId } = useAuth()
  // Mock mode simulates live updates locally (lunch-rush replay, Step 3) —
  // no real websocket in that mode. No socket until the owner has a restaurant.
  useInboxSocket(!USE_MOCKS && isAuthenticated && !isFounder && !!activeTenantId)

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset className="gap-0 p-0">
        <div className="flex h-svh flex-1 flex-col overflow-hidden">
          <DashboardTopbar />
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
