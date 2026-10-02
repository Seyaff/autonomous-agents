"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  BellIcon,
  FileTextIcon,
  InboxIcon,
  SendIcon,
  SettingsIcon,
  TrashIcon,
  UsersIcon,
} from "lucide-react"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { cn } from "@/lib/utils"

const navItems = [
  { title: "Inbox", slug: "inbox", icon: InboxIcon },
  { title: "Sent", slug: "sent", icon: SendIcon },
  { title: "Drafts", slug: "drafts", icon: FileTextIcon },
  { title: "Team", slug: "team", icon: UsersIcon },
  { title: "Trash", slug: "trash", icon: TrashIcon },
  { title: "Notifications", slug: "notifications", icon: BellIcon },
  { title: "Settings", slug: "settings", icon: SettingsIcon },
]

export const mails = Array.from({ length: 12 }).map((_, i) => ({
  id: `${i + 1}`,
  name: ["William Smith", "Alice Smith", "Bob Johnson", "Emily Davis", "Michael Wilson"][i % 5],
  email: `person${i}@example.com`,
  subject: [
    "Meeting Tomorrow",
    "Re: Project Update",
    "Weekend Plans",
    "Re: Question about Budget",
    "Important Announcement",
  ][i % 5],
  date: ["09:34 AM", "Yesterday", "2 days ago", "2 days ago", "1 week ago"][i % 5],
  teaser:
    "Hi team, just a reminder about our meeting tomorrow at 10 AM. Please review the notes attached before we start.",
}))

export function InboxSidebar() {
  const pathname = usePathname()
  const [activeIndex, setActiveIndex] = React.useState(0)
  const activeItem = navItems[activeIndex]

  return (
    <div className="flex h-full w-[420px] shrink-0 border-r bg-sidebar">
      {/* Icon rail */}
      <div className="flex w-14 shrink-0 flex-col items-center gap-1 border-r bg-sidebar py-3">
        {navItems.map((item, index) => {
          const Icon = item.icon
          const isActive = index === activeIndex
          return (
            <button
              key={item.title}
              onClick={() => setActiveIndex(index)}
              title={item.title}
              className={cn(
                "flex size-9 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                isActive && "bg-sidebar-accent text-sidebar-accent-foreground"
              )}
            >
              <Icon className="size-4" />
              <span className="sr-only">{item.title}</span>
            </button>
          )
        })}
      </div>

      {/* List panel */}
      <div className="flex  min-w-0 flex-1 h-screen flex-col">
        <div className="flex shrink-0 flex-col gap-3 border-b p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-medium">{activeItem.title}</h2>
            <Label className="flex items-center gap-2 text-sm">
              <span>Unreads</span>
              <Switch className="shadow-none" />
            </Label>
          </div>
          <Input placeholder="Type to search..." />
        </div>

        <div className="flex-1 overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {mails.map((mail) => {
            const href = `/dashboard/inbox/${mail.id}`
            const isActive = pathname === href
            return (
              <Link
                key={mail.id}
                href={href}
                className={cn(
                  "flex flex-col items-start gap-2 border-b p-4 text-sm leading-tight last:border-b-0 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                  isActive && "bg-sidebar-accent text-sidebar-accent-foreground"
                )}
              >
                <div className="flex w-full items-center gap-2">
                  <span className="font-medium">{mail.name}</span>
                  <span className="ml-auto text-xs text-muted-foreground">
                    {mail.date}
                  </span>
                </div>
                <span className="font-medium">{mail.subject}</span>
                <span className="line-clamp-2 text-xs text-muted-foreground">
                  {mail.teaser}
                </span>
              </Link>
            )
          })}
        </div>
      </div>
    </div>
  )
}