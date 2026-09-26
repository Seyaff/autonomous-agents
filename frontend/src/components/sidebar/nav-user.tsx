"use client"

import {
  Avatar,
  AvatarFallback,
  AvatarImage,
} from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import { useGetCurrentUser } from "@/hooks/auth/get-me"
import { EllipsisVerticalIcon, CircleUserRoundIcon, CreditCardIcon, BellIcon, LogOutIcon } from "lucide-react"
import { Skeleton } from "../ui/skeleton"

type User = {
  email: string
  full_name: string
  profile_picture?: string
}

export function NavUser({
  user,
}: {
  user?: {
    name: string
    email: string
    avatar: string
  }
}) {
  const { isMobile } = useSidebar()
  const { data: bro, isPending } = useGetCurrentUser()

  const ourbro: User | undefined = bro

  const getInitials = (name?: string) => {
    if (!name) return "U"
    return name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2)
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <SidebarMenuButton size="lg" className="aria-expanded:bg-muted" />
            }
          >
            {isPending ? (
              // --- SKELETON LOADING STATE FOR TRIGGER ---
              <div className="flex w-full items-center gap-2">
                <Skeleton className="size-8 rounded-lg" />
                <div className="grid flex-1 gap-1">
                  <Skeleton className="h-3.5 w-24" />
                  <Skeleton className="h-2.5 w-32" />
                </div>
              </div>
            ) : (
              // --- ACTUAL USER TRIGGER DATA ---
              <>
                <Avatar className="size-8 rounded-lg">
                  <AvatarImage src={ourbro?.profile_picture || user?.avatar} alt={ourbro?.full_name} />
                  <AvatarFallback className="rounded-lg">
                    {getInitials(ourbro?.full_name)}
                  </AvatarFallback>
                </Avatar>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-medium">{ourbro?.full_name}</span>
                  <span className="truncate text-xs text-foreground/70">
                    {ourbro?.email}
                  </span>
                </div>
                <EllipsisVerticalIcon className="ml-auto size-4" />
              </>
            )}
          </DropdownMenuTrigger>
          
          <DropdownMenuContent
            className="min-w-56"
            side={isMobile ? "bottom" : "right"}
            align="end"
            sideOffset={4}
          >
            <DropdownMenuGroup>
              <DropdownMenuLabel className="p-0 font-normal">
                <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                  {isPending ? (
                    // --- SKELETON LOADING STATE FOR DROPDOWN HEADER ---
                    <div className="flex w-full items-center gap-2">
                      <Skeleton className="size-8 rounded-lg" />
                      <div className="grid flex-1 gap-1">
                        <Skeleton className="h-3.5 w-24" />
                        <Skeleton className="h-2.5 w-32" />
                      </div>
                    </div>
                  ) : (
                    // --- ACTUAL DROPDOWN HEADER DATA ---
                    <>
                      <Avatar className="size-8 rounded-lg">
                        <AvatarImage src={ourbro?.profile_picture || user?.avatar} alt={ourbro?.full_name} />
                        <AvatarFallback className="rounded-lg">
                          {getInitials(ourbro?.full_name)}
                        </AvatarFallback>
                      </Avatar>
                      <div className="grid flex-1 text-left text-sm leading-tight">
                        <span className="truncate font-medium">{ourbro?.full_name}</span>
                        <span className="truncate text-xs text-muted-foreground">
                          {ourbro?.email}
                        </span>
                      </div>
                    </>
                  )}
                </div>
              </DropdownMenuLabel>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem>
                <CircleUserRoundIcon />
                Account
              </DropdownMenuItem>
              <DropdownMenuItem>
                <CreditCardIcon />
                Billing
              </DropdownMenuItem>
              <DropdownMenuItem>
                <BellIcon />
                Notifications
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem>
              <LogOutIcon />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}