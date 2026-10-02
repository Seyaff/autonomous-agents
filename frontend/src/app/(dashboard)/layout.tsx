"use client"

import { AppSidebar } from "@/components/sidebar/app-sidebar"
import {
  SidebarInset,
  SidebarProvider,
} from "@/components/ui/sidebar"
import { useAuth } from "@/components/providers/auth-provider"
import { useInboxSocket } from "@/hooks/inbox/use-inbox-socket"

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const { isAuthenticated, isFounder } = useAuth()
  useInboxSocket(isAuthenticated && !isFounder)

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset className="gap-0 p-0">
        <div className="flex h-svh flex-1 flex-col overflow-hidden">
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
