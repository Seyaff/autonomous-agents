"use client"

import { AppSidebar } from "@/components/sidebar/app-sidebar"
import { DashboardTopbar } from "@/components/dashboard/dashboard-topbar"
import {
  SidebarInset,
  SidebarProvider,
} from "@/components/ui/sidebar"
import { useAuth } from "@/components/providers/auth-provider"
import { useInboxSocket } from "@/hooks/inbox/use-inbox-socket"
import { BillingBanner } from "@/components/billing/billing-banner"
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
      <meta name="robots" content="noindex, nofollow" />
      <AppSidebar />
      <SidebarInset className="min-h-0 gap-0 p-0 overflow-hidden">
        <div className="flex h-svh min-h-0 flex-1 flex-col overflow-hidden">
          <DashboardTopbar />
          <BillingBanner />
          <div className="flex min-h-0 flex-1 flex-col">{children}</div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
