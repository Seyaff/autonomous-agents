"use client"

import * as React from "react"
import { usePathname } from "next/navigation"
import {
  BarChart3Icon,
  BookOpenIcon,
  CreditCardIcon,
  UsersIcon,
  HomeIcon,
  InboxIcon,
  ReceiptTextIcon,
  SettingsIcon,
  SparklesIcon,
} from "lucide-react"

import { TenantSwitcher } from "@/components/sidebar/tenant-switcher"
import { NavMain, type NavMainItem } from "@/components/sidebar/nav-main"
import { NavUser } from "@/components/sidebar/nav-user"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar"
import { useUnreadTotal } from "@/hooks/inbox/use-unread-total"
import { useSetupReminders } from "@/hooks/setup/use-setup-reminders"

const INBOX_PREFIX = "/dashboard/inbox"

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const { setOpen } = useSidebar()
  const pathname = usePathname()
  const unreadTotal = useUnreadTotal()
  const { remaining: setupRemaining } = useSetupReminders()

  const navMain: NavMainItem[] = [
    {
      title: "Live service",
      url: "/dashboard",
      icon: <HomeIcon />,
      badge: setupRemaining.length > 0 ? String(setupRemaining.length) : undefined,
    },
    {
      title: "Inbox",
      url: "/dashboard/inbox",
      icon: <InboxIcon />,
      badge: unreadTotal > 0 ? String(unreadTotal) : undefined,
    },
    { title: "Orders", url: "/dashboard/orders", icon: <ReceiptTextIcon /> },
    { title: "Menu knowledge", url: "/dashboard/menu", icon: <BookOpenIcon /> },
    { title: "Customers", url: "/dashboard/customers", icon: <UsersIcon /> },
    { title: "Reports", url: "/dashboard/reports", icon: <BarChart3Icon /> },
    { title: "Billing", url: "/dashboard/billing", icon: <CreditCardIcon /> },
    { title: "Assistant", url: "/dashboard/assistant", icon: <SparklesIcon /> },
    { title: "Settings", url: "/dashboard/settings", icon: <SettingsIcon /> },
  ]

  const isInbox = pathname === INBOX_PREFIX || pathname.startsWith(`${INBOX_PREFIX}/`)
  const prevPathname = React.useRef<string | null>(null)

  React.useEffect(() => {
    const prev = prevPathname.current
    const wasInbox =
      prev === INBOX_PREFIX || (prev?.startsWith(`${INBOX_PREFIX}/`) ?? false)

    // Entering inbox → collapse
    if (isInbox && !wasInbox) {
      setOpen(false)
    }

    // Leaving inbox → expand
    if (!isInbox && wasInbox) {
      setOpen(true)
    }

    prevPathname.current = pathname
  }, [isInbox, pathname, setOpen])

  // Hover-to-expand only while in inbox
  const handleMouseEnter = () => {
    if (isInbox) setOpen(true)
  }

  const handleMouseLeave = () => {
    if (isInbox) setOpen(false)
  }

  return (
    <Sidebar
      collapsible="icon"
      className="border-r-0 fixed left-0 top-0 z-50 h-svh"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      {...props}
    >
      <SidebarHeader>
        <TenantSwitcher />
        <NavMain items={navMain} />
      </SidebarHeader>
      <SidebarContent />
      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
