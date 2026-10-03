"use client"

import * as React from "react"
import { Building2Icon, ChevronDownIcon } from "lucide-react"

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import { useAuth } from "@/components/providers/auth-provider"
import { useCurrentTenant } from "@/hooks/tenant/use-current-tenant"
import { Skeleton } from "@/components/ui/skeleton"
import { MOCK_ACTIVE_TENANT_ID, MOCK_TENANTS } from "@/lib/mock/tenant"
import { USE_MOCKS } from "@/lib/mocks"
import type { TenantSummary } from "@/services/tenant/tenant.service"

export function TenantSwitcher() {
  const { tenants, activeTenantId, switchTenant } = useAuth()
  const { data: activeTenant } = useCurrentTenant()
  const [mockActiveId, setMockActiveId] = React.useState(MOCK_ACTIVE_TENANT_ID)

  const options: TenantSummary[] = USE_MOCKS
    ? MOCK_TENANTS
    : tenants.map((id) => ({
        tenant_id: id,
        business_name: id === activeTenantId ? activeTenant?.business_name ?? id : id,
        currency: activeTenant?.currency ?? "USD",
      }))

  const currentId = USE_MOCKS ? mockActiveId : activeTenantId
  const current = options.find((t) => t.tenant_id === currentId) ?? options[0]

  async function handleSelect(tenantId: string) {
    if (tenantId === currentId) return
    if (USE_MOCKS) {
      setMockActiveId(tenantId)
      return
    }
    await switchTenant(tenantId)
  }

  if (!current) {
    return (
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton
            size="lg"
            className="cursor-default hover:bg-transparent active:bg-transparent"
          >
            <div className="flex aspect-square size-8 items-center justify-center rounded-md bg-sidebar-primary text-sidebar-primary-foreground">
              <Building2Icon className="size-4" />
            </div>
            <div className="grid flex-1 text-left leading-tight">
              <span className="truncate text-sm font-semibold">Your Restaurant</span>
              <span className="truncate text-xs text-muted-foreground">
                Siyaf Autopilot
              </span>
            </div>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    )
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <SidebarMenuButton
                size="lg"
                className="data-open:bg-sidebar-accent data-open:text-sidebar-accent-foreground"
              />
            }
          >
            <div className="flex aspect-square size-8 items-center justify-center rounded-md bg-sidebar-primary text-sidebar-primary-foreground">
              <Building2Icon className="size-4" />
            </div>
            <div className="grid flex-1 text-left leading-tight">
              <span className="truncate text-sm font-semibold">
                {current ? (
                  `${current.business_name}${current.branch_name ? ` · ${current.branch_name}` : ""}`
                ) : (
                  <Skeleton className="h-4 w-32" />
                )}
              </span>
              <span className="truncate text-xs text-muted-foreground">
                {options.length > 1 ? `${options.length} branches` : "Siyaf Autopilot"}
              </span>
            </div>
            <ChevronDownIcon className="ml-auto size-4 text-muted-foreground" />
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-64 rounded-lg" align="start" side="bottom" sideOffset={4}>
            <DropdownMenuLabel className="text-xs text-muted-foreground">
              {options.length} {options.length === 1 ? "branch" : "branches"}
            </DropdownMenuLabel>
            {options.map((t) => (
              <DropdownMenuItem key={t.tenant_id} onClick={() => handleSelect(t.tenant_id)}>
                <span className="text-sm font-medium">
                  {t.business_name}
                  {t.branch_name ? ` · ${t.branch_name}` : ""}
                </span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
