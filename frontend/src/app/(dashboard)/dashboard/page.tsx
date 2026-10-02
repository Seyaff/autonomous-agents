"use client"

import { DashboardHeader } from "@/components/dashboard/dashboard-header"
import { OrdersTable } from "@/components/dashboard/data-table"
import { use7DaySummary } from "@/hooks/analytics/use-7day-summary"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { ArrowDownIcon, ArrowUpIcon } from "lucide-react"
import { cn } from "@/lib/utils"

const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
})

export default function DashboardPage() {
  const { data: metrics, isLoading } = use7DaySummary()

  const stats = [
    {
      label: "Conversations",
      value: metrics?.total_conversations ?? 0,
    },
    {
      label: "Messages",
      value: metrics?.total_messages ?? 0,
    },
    {
      label: "Revenue (7d)",
      value: currencyFormatter.format(metrics?.total_revenue ?? 0),
      delta: metrics?.revenue_growth_pct,
    },
    {
      label: "Orders (7d)",
      value: metrics?.total_orders ?? 0,
    },
  ]

  return (
    <main className="flex flex-1 flex-col gap-6 p-6 pt-0">
      <DashboardHeader />

      <div className="grid auto-rows-min gap-4 md:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.label} className="h-24">
            <CardHeader className="flex h-full flex-col justify-between p-4">
              <CardTitle className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                {stat.label}
              </CardTitle>
              <CardContent className="flex items-end justify-between p-0">
                {isLoading ? (
                  <Skeleton className="h-9 w-20" />
                ) : (
                  <p className="text-4xl font-semibold tracking-tight tabular-nums">
                    {stat.value}
                  </p>
                )}
                {stat.delta !== undefined && !isLoading && (
                  <span
                    className={cn(
                      "flex items-center gap-0.5 text-xs font-medium tabular-nums",
                      stat.delta >= 0
                        ? "text-(--status-success-fg)"
                        : "text-(--status-danger-fg)"
                    )}
                  >
                    {stat.delta >= 0 ? (
                      <ArrowUpIcon className="size-3" />
                    ) : (
                      <ArrowDownIcon className="size-3" />
                    )}
                    {Math.abs(stat.delta).toFixed(1)}%
                  </span>
                )}
              </CardContent>
            </CardHeader>
          </Card>
        ))}
      </div>

      <OrdersTable />
    </main>
  )
}
