"use client"

import { LogOutIcon, SparklesIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { useAuth } from "@/components/providers/auth-provider"

export default function FounderLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const { user, logout } = useAuth()

  return (
    <div className="flex min-h-svh flex-col bg-background">
      <header className="flex shrink-0 items-center justify-between border-b px-6 py-3">
        <div className="flex items-center gap-2">
          <div className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <SparklesIcon className="size-4" />
          </div>
          <div className="flex flex-col leading-tight">
            <span className="text-sm font-semibold">Founder Console</span>
            <span className="text-xs text-muted-foreground">
              {user?.full_name}
            </span>
          </div>
        </div>
        <Button variant="ghost" size="sm" onClick={() => logout()} className="gap-2">
          <LogOutIcon className="size-4" />
          Log out
        </Button>
      </header>
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  )
}
