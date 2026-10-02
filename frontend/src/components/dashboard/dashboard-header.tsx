"use client"

import { useAuth } from "@/components/providers/auth-provider"

function greeting() {
  const hour = new Date().getHours()
  if (hour < 12) return "Good morning"
  if (hour < 18) return "Good afternoon"
  return "Good evening"
}

export function DashboardHeader() {
  const { user } = useAuth()
  const firstName = user?.full_name?.split(" ")[0] ?? ""

  return (
    <div className="flex flex-col gap-1 pt-6 pb-2">
      <h1 className="text-2xl font-semibold tracking-tight">
        {greeting()}
        {firstName ? `, ${firstName}` : ""}
      </h1>
      <p className="text-sm text-muted-foreground">
        Here&apos;s what&apos;s happening at your restaurant this week.
      </p>
    </div>
  )
}
