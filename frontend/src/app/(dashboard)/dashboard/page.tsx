// src/app/dashboard/page.tsx
import { DashboardHeader } from "@/components/dashboard/dashboard-header"
import { OrdersTable } from "@/components/dashboard/data-table"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

const stats = [
  { label: "Conversations", value: "234" },
  { label: "Messages", value: "2,399" },
  { label: "Profit", value: "$2,938" },
  { label: "Orders", value: "123" },
]

export default function DashboardPage() {
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
              <CardContent className="p-0">
                <p className="text-4xl font-semibold tracking-tight tabular-nums">
                  {stat.value}
                </p>
              </CardContent>
            </CardHeader>
          </Card>
        ))}
      </div>

      <OrdersTable />
    </main>
  )
}