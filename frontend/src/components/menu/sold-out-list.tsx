"use client"

import * as React from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useMenuItems } from "@/hooks/setup/use-menu-items"
import API from "@/lib/axios-client"

/**
 * Today's dishes. Marking one sold out keeps the agent from offering or ordering it.
 * It comes back on its own the next day.
 */
export function SoldOutList() {
  const menu = useMenuItems()
  const queryClient = useQueryClient()
  const [pending, setPending] = React.useState<string | null>(null)

  const toggle = useMutation({
    mutationFn: async ({ name, soldOut }: { name: string; soldOut: boolean }) => {
      await API.post("/tenant/current/menu-items/sold-out", { name, sold_out: soldOut })
      return soldOut
    },
    onSuccess: (soldOut, { name }) => {
      toast(soldOut ? `${name} is sold out for today. The agent won't offer it.` : `${name} is back on the menu.`)
      queryClient.invalidateQueries({ queryKey: ["tenant", "menu-items"] })
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail ?? "Could not update that dish."),
    onSettled: () => setPending(null),
  })

  const items = menu.data?.items ?? []
  if (menu.isLoading || items.length === 0) return null

  const soldOutCount = items.filter((i) => i.sold_out_today).length

  return (
    <section className="border-b border-border px-4 py-3">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-medium">Dishes today</h2>
        {soldOutCount > 0 && <Badge variant="outline">{soldOutCount} sold out</Badge>}
      </div>
      <ul className="divide-y divide-border">
        {items.map((item) => (
          <li key={`${item.category ?? ""}-${item.name}`} className="flex items-center justify-between gap-3 py-2">
            <div className="min-w-0">
              <p className={`truncate text-sm ${item.sold_out_today ? "text-muted-foreground line-through" : ""}`}>
                {item.name}
              </p>
              {item.category && <p className="font-mono text-[11px] text-muted-foreground">{item.category}</p>}
            </div>
            <Button
              size="sm"
              variant={item.sold_out_today ? "outline" : "ghost"}
              disabled={toggle.isPending && pending === item.name}
              onClick={() => {
                setPending(item.name)
                toggle.mutate({ name: item.name, soldOut: !item.sold_out_today })
              }}
            >
              {item.sold_out_today ? "Back on the menu" : "Sold out today"}
            </Button>
          </li>
        ))}
      </ul>
    </section>
  )
}
