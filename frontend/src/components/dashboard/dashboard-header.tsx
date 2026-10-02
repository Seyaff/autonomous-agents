// src/components/dashboard/dashboard-header.tsx
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Separator } from "@/components/ui/separator"
import { BellIcon, ChevronDownIcon, PlusIcon, SettingsIcon } from "lucide-react"

export function DashboardHeader() {
  return (
    <div className="flex flex-col gap-4 pt-6 pb-2 sm:flex-row sm:items-center sm:justify-between">
      {/* Left: greeting + subtitle */}
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">
          Good evening, Ayesha
        </h1>
        <p className="text-sm text-muted-foreground">
          Here&apos;s what&apos;s happening at your restaurant today.
        </p>
      </div>

      {/* Right: actions + user */}
      <div className="flex items-center gap-3">
        <Button variant="outline" size="sm" className="gap-2">
          <BellIcon className="size-4" />
          <span className="hidden sm:inline">Notifications</span>
          <Badge variant="secondary" className="ml-1 h-4 px-1 text-[10px]">
            3
          </Badge>
        </Button>
        <Button size="sm" className="gap-2">
          <PlusIcon className="size-4" />
          <span className="hidden sm:inline">New Order</span>
        </Button>

        <Separator orientation="vertical" className="h-8" />

        <DropdownMenu>
          <DropdownMenuTrigger className="flex items-center gap-2 rounded-md p-1 pr-2 transition-colors hover:bg-accent">
            <Avatar className="size-8">
              <AvatarImage src="" alt="Ayesha" />
              <AvatarFallback className="text-xs">AK</AvatarFallback>
            </Avatar>
            <div className="hidden flex-col items-start text-left sm:flex">
              <span className="text-sm leading-none font-medium">
                Ayesha Khan
              </span>
              <span className="text-xs leading-none text-muted-foreground">
                Manager
              </span>
            </div>
            <ChevronDownIcon className="size-4 text-muted-foreground" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuItem>Profile</DropdownMenuItem>
            <DropdownMenuItem>Billing</DropdownMenuItem>
            <DropdownMenuItem>Team</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem>
              <SettingsIcon className="mr-2 size-4" />
              Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive">Log out</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  )
}