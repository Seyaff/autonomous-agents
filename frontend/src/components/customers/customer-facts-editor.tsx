"use client"

import * as React from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  correctCustomerFact,
  forgetCustomerFact,
  listCustomerFacts,
  type CustomerFactRow,
} from "@/services/customers/customers.service"

function errorText(err: unknown, fallback: string) {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback
}

/** What the agent remembers about this customer. The owner can correct a fact or make the agent forget it. */
export function CustomerFactsEditor({ phone }: { phone: string }) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = React.useState<string | null>(null)
  const [draft, setDraft] = React.useState("")

  const facts = useQuery({
    queryKey: ["customers", "facts", phone],
    queryFn: () => listCustomerFacts(phone),
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["customers", "facts", phone] })
    queryClient.invalidateQueries({ queryKey: ["customers"] })
  }

  const correct = useMutation({
    mutationFn: ({ id, value }: { id: string; value: string }) => correctCustomerFact(phone, id, value),
    onSuccess: () => {
      toast("Saved. The agent will use this from now on.")
      setEditing(null)
      refresh()
    },
    onError: (err) => toast.error(errorText(err, "Could not save that.")),
  })

  const forget = useMutation({
    mutationFn: (id: string) => forgetCustomerFact(phone, id),
    onSuccess: () => {
      toast("The agent won't use that any more.")
      refresh()
    },
    onError: (err) => toast.error(errorText(err, "Could not remove that.")),
  })

  const rows: CustomerFactRow[] = facts.data ?? []

  return (
    <section className="space-y-2">
      <h2 className="font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground">What the agent remembers</h2>
      {facts.isLoading ? null : rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nothing noted yet. Preferences and allergies appear here as customers mention them.</p>
      ) : (
        <ul className="space-y-2">
          {rows.map((f) => (
            <li key={f.id} className="text-sm">
              {editing === f.id ? (
                <div className="flex gap-2">
                  <Input
                    aria-label={`Correct ${f.kind}`}
                    value={draft}
                    maxLength={200}
                    onChange={(e) => setDraft(e.target.value)}
                  />
                  <Button size="sm" disabled={!draft.trim() || correct.isPending} onClick={() => correct.mutate({ id: f.id, value: draft })}>
                    Save
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
                </div>
              ) : (
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="mr-2 font-mono text-[11px] uppercase text-muted-foreground">{f.kind}</span>
                    {f.value}
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <Button size="sm" variant="ghost" onClick={() => { setEditing(f.id); setDraft(f.value) }}>Correct</Button>
                    <Button size="sm" variant="ghost" disabled={forget.isPending} onClick={() => forget.mutate(f.id)}>Forget</Button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
