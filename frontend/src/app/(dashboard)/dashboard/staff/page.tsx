"use client"

import * as React from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  addStaff,
  listStaff,
  removeStaff,
  resetStaffPin,
  setTableCount,
  unlockStaff,
  type StaffRole,
} from "@/services/staff/staff.service"

const ROLE_LABEL: Record<StaffRole, string> = { waiter: "Waiter", reception: "Reception", kitchen: "Kitchen" }

function errorText(err: unknown, fallback: string) {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback
}

export default function StaffPage() {
  const queryClient = useQueryClient()
  const data = useQuery({ queryKey: ["owner", "staff"], queryFn: listStaff })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["owner", "staff"] })

  const [name, setName] = React.useState("")
  const [role, setRole] = React.useState<StaffRole>("waiter")
  const [pin, setPin] = React.useState("")
  const [tables, setTables] = React.useState("")
  const [resetPins, setResetPins] = React.useState<Record<string, string>>({})

  const add = useMutation({
    mutationFn: () => addStaff({ name: name.trim(), role, pin }),
    onSuccess: (s) => {
      toast.success(`${s.name} added. Tell ${s.name} the PIN ${pin} in person.`)
      setName(""); setPin("")
      refresh()
    },
    onError: (err) => toast.error(errorText(err, "Could not add them.")),
  })
  const reset = useMutation({
    mutationFn: (args: { id: string; pin: string }) => resetStaffPin(args.id, args.pin),
    onSuccess: (_s, args) => {
      toast.success(`New PIN ${args.pin} set. Tell them in person.`)
      setResetPins((p) => ({ ...p, [args.id]: "" }))
      refresh()
    },
    onError: (err) => toast.error(errorText(err, "Could not reset the PIN.")),
  })
  const unlock = useMutation({
    mutationFn: (id: string) => unlockStaff(id),
    onSuccess: () => { toast.success("Unlocked."); refresh() },
    onError: (err) => toast.error(errorText(err, "Could not unlock.")),
  })
  const remove = useMutation({
    mutationFn: (id: string) => removeStaff(id),
    onSuccess: () => { toast.success("Removed. Their iPad is signed out."); refresh() },
    onError: (err) => toast.error(errorText(err, "Could not remove them.")),
  })
  const saveTables = useMutation({
    mutationFn: (count: number) => setTableCount(count),
    onSuccess: (r) => { toast.success(`${r.count} tables set up.`); setTables(""); refresh() },
    onError: (err) => toast.error(errorText(err, "Could not save the table count.")),
  })

  const canAdd = name.trim().length > 0 && /^\d{4}$/.test(pin) && !add.isPending

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 p-4">
      <div>
        <h1 className="text-lg font-semibold">Staff and tables</h1>
        <p className="text-sm text-muted-foreground">One waiter, one iPad. You set each PIN and tell the person in person.</p>
      </div>

      <section className="grid gap-3 rounded-xl border border-border bg-card p-4">
        <h2 className="font-medium">Tables</h2>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-muted-foreground">Set up now: {data.data?.table_count ?? 0} tables</span>
          <Input
            className="w-28"
            inputMode="numeric"
            placeholder="How many"
            value={tables}
            onChange={(e) => setTables(e.target.value.replace(/\D/g, ""))}
            aria-label="Number of tables"
          />
          <Button onClick={() => saveTables.mutate(Number(tables))} disabled={!tables || saveTables.isPending}>Save tables</Button>
        </div>
      </section>

      <section className="grid gap-3 rounded-xl border border-border bg-card p-4">
        <h2 className="font-medium">Add a staff member</h2>
        <form
          className="grid gap-3 sm:grid-cols-[1fr_auto_auto_auto] sm:items-end"
          onSubmit={(e) => { e.preventDefault(); if (canAdd) add.mutate() }}
        >
          <label className="grid gap-1 text-sm">
            <span>Name</span>
            <Input value={name} maxLength={40} onChange={(e) => setName(e.target.value)} placeholder="e.g. Bilal" />
          </label>
          <label className="grid gap-1 text-sm">
            <span>Role</span>
            <select value={role} onChange={(e) => setRole(e.target.value as StaffRole)} className="h-9 rounded-md border border-input bg-background px-2">
              <option value="waiter">Waiter</option>
              <option value="reception">Reception</option>
              <option value="kitchen">Kitchen</option>
            </select>
          </label>
          <label className="grid gap-1 text-sm">
            <span>4-digit PIN</span>
            <Input inputMode="numeric" maxLength={4} value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, "").slice(0, 4))} className="w-28" />
          </label>
          <Button type="submit" disabled={!canAdd}>Add</Button>
        </form>
      </section>

      <section className="grid gap-3">
        <h2 className="font-medium">Staff</h2>
        {data.isPending && <p className="text-sm text-muted-foreground">Loading…</p>}
        {data.data?.staff.length === 0 && <p className="text-sm text-muted-foreground">No staff yet.</p>}
        {data.data?.staff.map((s) => (
          <article key={s.staff_id} className="grid gap-2 rounded-xl border border-border bg-card p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <strong>{s.name}</strong>
              <span className="text-xs text-muted-foreground">{ROLE_LABEL[s.role]} · {s.status}</span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Input
                className="w-28"
                inputMode="numeric"
                maxLength={4}
                placeholder="New PIN"
                aria-label={`New PIN for ${s.name}`}
                value={resetPins[s.staff_id] ?? ""}
                onChange={(e) => setResetPins((p) => ({ ...p, [s.staff_id]: e.target.value.replace(/\D/g, "").slice(0, 4) }))}
              />
              <Button
                variant="outline"
                disabled={!/^\d{4}$/.test(resetPins[s.staff_id] ?? "") || reset.isPending}
                onClick={() => reset.mutate({ id: s.staff_id, pin: resetPins[s.staff_id] })}
              >
                Reset PIN
              </Button>
              {s.locked && <Button variant="outline" onClick={() => unlock.mutate(s.staff_id)} disabled={unlock.isPending}>Unlock</Button>}
              <Button variant="ghost" onClick={() => remove.mutate(s.staff_id)} disabled={remove.isPending}>Remove</Button>
            </div>
          </article>
        ))}
      </section>
    </div>
  )
}
