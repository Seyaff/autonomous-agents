"use client"

import * as React from "react"
import { usePathname } from "next/navigation"
import { HomeIcon, InboxIcon } from "lucide-react"

import { BrandHeader } from "@/components/sidebar/brand-header"
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

const INBOX_PREFIX = "/dashboard/inbox"

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const { setOpen } = useSidebar()
  const pathname = usePathname()
  const unreadTotal = useUnreadTotal()

  const navMain: NavMainItem[] = [
    { title: "Dashboard", url: "/dashboard", icon: <HomeIcon /> },
    {
      title: "Inbox",
      url: "/dashboard/inbox",
      icon: <InboxIcon />,
      badge: unreadTotal > 0 ? String(unreadTotal) : undefined,
    },
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
        <BrandHeader />
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
