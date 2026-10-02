"use client"

import * as React from "react"
import { LayoutGridIcon, TableIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { OrdersRail } from "@/components/orders/orders-rail"
import { OrdersLedger } from "@/components/orders/orders-ledger"
import { useRail } from "@/hooks/console/use-rail"
import { useCurrentTenant } from "@/hooks/tenant/use-current-tenant"

export default function OrdersPage() {
  const [view, setView] = React.useState<"rail" | "ledger">("rail")

  const { data: tenant } = useCurrentTenant()
  const currency = tenant?.currency ?? "USD"

  const { orders, isLoading, advance } = useRail()

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="flex shrink-0 items-center justify-between border-b border-border bg-card px-4 py-2">
        <div>
          <h1 className="text-sm font-medium">Orders</h1>
          <p className="font-mono text-[11px] text-muted-foreground">
            {view === "rail" ? "Today, by status" : "Full order history"}
          </p>
        </div>
        <div className="flex items-center gap-1 rounded-md border border-border p-0.5">
          <Button
            variant={view === "rail" ? "secondary" : "ghost"}
            size="sm"
            className="gap-1.5"
            onClick={() => setView("rail")}
          >
            <LayoutGridIcon className="size-3.5" />
            Rail
          </Button>
          <Button
            variant={view === "ledger" ? "secondary" : "ghost"}
            size="sm"
            className="gap-1.5"
            onClick={() => setView("ledger")}
          >
            <TableIcon className="size-3.5" />
            Ledger
          </Button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-hidden">
        {view === "rail" ? (
          <OrdersRail orders={orders} currency={currency} isLoading={isLoading} onAdvance={advance} />
        ) : (
          <div className="h-full overflow-y-auto">
            <OrdersLedger orders={orders} currency={currency} isLoading={isLoading} onAdvance={advance} />
          </div>
        )}
      </div>
    </div>
  )
}
