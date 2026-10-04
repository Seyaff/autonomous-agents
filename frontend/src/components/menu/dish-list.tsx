"use client"

import * as React from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { useMenuItems } from "@/hooks/setup/use-menu-items"
import API from "@/lib/axios-client"
import type { MenuItem } from "@/services/setup/setup.service"

type Fields = { name: string; category: string; price: string; description: string }

const EMPTY: Fields = { name: "", category: "", price: "", description: "" }

function errorText(err: unknown, fallback: string) {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback
}

function toPayload(f: Fields) {
  return {
    name: f.name.trim(),
    category: f.category.trim() || null,
    price: f.price.trim() === "" ? null : Number(f.price),
    description: f.description.trim(),
  }
}

/** The dishes the agent reads from. The owner can fix names and prices, hide a dish, or mark it sold out today. */
export function DishList() {
  const menu = useMenuItems()
  const queryClient = useQueryClient()
  const [editing, setEditing] = React.useState<MenuItem | "new" | null>(null)
  const [fields, setFields] = React.useState<Fields>(EMPTY)

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["tenant", "menu-items"] })

  const soldOut = useMutation({
    mutationFn: async ({ name, on }: { name: string; on: boolean }) =>
      API.post("/tenant/current/menu-items/sold-out", { name, sold_out: on }),
    onSuccess: (_, { on, name }) => {
      toast(on ? `${name} is sold out for today.` : `${name} is back on the menu.`)
      refresh()
    },
    onError: (err) => toast.error(errorText(err, "Could not update that dish.")),
  })

  const patch = useMutation({
    mutationFn: async ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      API.patch(`/tenant/current/menu-items/${id}`, body),
    onSuccess: () => refresh(),
    onError: (err) => toast.error(errorText(err, "Could not save that dish.")),
  })

  const save = useMutation({
    mutationFn: async () => {
      const body = toPayload(fields)
      if (editing === "new") return API.post("/tenant/current/menu-items", { ...body, hidden: false })
      if (editing) return API.patch(`/tenant/current/menu-items/${editing.id}`, body)
    },
    onSuccess: () => {
      toast("Dish saved. The agent uses the new details now.")
      setEditing(null)
      refresh()
    },
    onError: (err) => toast.error(errorText(err, "Could not save that dish.")),
  })

  const remove = useMutation({
    mutationFn: async (id: string) => API.delete(`/tenant/current/menu-items/${id}`),
    onSuccess: () => {
      toast("Dish removed.")
      setEditing(null)
      refresh()
    },
    onError: (err) => toast.error(errorText(err, "Could not remove that dish.")),
  })

  function openEdit(item: MenuItem) {
    setFields({
      name: item.name,
      category: item.category ?? "",
      price: item.price == null ? "" : String(item.price),
      description: item.description ?? "",
    })
    setEditing(item)
  }

  function openNew() {
    setFields(EMPTY)
    setEditing("new")
  }

  const items = menu.data?.items ?? []
  if (menu.isLoading) return null

  const groups = items.reduce<Record<string, MenuItem[]>>((acc, item) => {
    const key = item.category || "Other"
    ;(acc[key] ??= []).push(item)
    return acc
  }, {})

  const canSave = fields.name.trim().length >= 2 && fields.price.trim() !== "" && !Number.isNaN(Number(fields.price))

  return (
    <section className="border-b border-border px-4 py-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="text-sm font-medium">Dishes</h2>
        <Button size="sm" variant="outline" onClick={openNew}>Add a dish</Button>
      </div>

      {items.length === 0 ? (
        <p className="rounded-md border border-dashed p-3 font-mono text-xs text-muted-foreground">
          No dishes yet. Upload a menu above, or add dishes one by one.
        </p>
      ) : (
        <div className="space-y-4">
          {Object.entries(groups).map(([category, dishes]) => (
            <div key={category}>
              <p className="mb-1 font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground">{category}</p>
              <ul className="divide-y divide-border">
                {dishes.map((item) => (
                  <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                    <div className="min-w-0">
                      <p className={`truncate text-sm ${item.hidden || item.sold_out_today ? "text-muted-foreground" : ""}`}>
                        {item.name}
                        {item.price != null && <span className="ml-2 font-mono text-xs">{item.price.toLocaleString()}</span>}
                      </p>
                      <div className="mt-0.5 flex gap-1">
                        {item.hidden && <Badge variant="outline">Hidden from agent</Badge>}
                        {item.sold_out_today && <Badge variant="outline">Sold out today</Badge>}
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      <Button size="sm" variant="ghost" onClick={() => openEdit(item)}>Edit</Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={patch.isPending}
                        onClick={() => patch.mutate({ id: item.id, body: { hidden: !item.hidden } })}
                      >
                        {item.hidden ? "Show to agent" : "Hide from agent"}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={soldOut.isPending}
                        onClick={() => soldOut.mutate({ name: item.name, on: !item.sold_out_today })}
                      >
                        {item.sold_out_today ? "Back on the menu" : "Sold out today"}
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      <Dialog open={editing !== null} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="sm:max-w-[460px]">
          <DialogHeader>
            <DialogTitle className="font-display">{editing === "new" ? "Add a dish" : "Edit dish"}</DialogTitle>
            <DialogDescription>Changes go straight to the agent's dish list.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <Label htmlFor="dish-name">Name</Label>
              <Input id="dish-name" value={fields.name} onChange={(e) => setFields({ ...fields, name: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="dish-category">Category</Label>
                <Input id="dish-category" placeholder="e.g. Mains" value={fields.category} onChange={(e) => setFields({ ...fields, category: e.target.value })} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="dish-price">Price</Label>
                <Input id="dish-price" inputMode="decimal" value={fields.price} onChange={(e) => setFields({ ...fields, price: e.target.value })} />
              </div>
            </div>
            <div className="space-y-1">
              <Label htmlFor="dish-description">Description (optional)</Label>
              <Textarea id="dish-description" rows={2} value={fields.description} onChange={(e) => setFields({ ...fields, description: e.target.value })} />
            </div>
          </div>
          <DialogFooter className="sm:justify-between">
            {editing && editing !== "new" ? (
              <Button variant="ghost" className="text-need" disabled={remove.isPending} onClick={() => remove.mutate(editing.id)}>
                Remove dish
              </Button>
            ) : <span />}
            <Button disabled={!canSave || save.isPending} onClick={() => save.mutate()}>
              {save.isPending ? "Saving…" : "Save dish"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  )
}
