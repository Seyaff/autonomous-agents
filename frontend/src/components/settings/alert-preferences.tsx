"use client"

import * as React from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import API from "@/lib/axios-client"

type AlertKind = { kind: string; label: string; description: string; whatsapp: boolean }
type AlertPrefs = { owner_phone: string | null; kinds: AlertKind[] }

/** Which alerts reach the owner on WhatsApp. Everything else still shows in the dashboard. */
export function AlertPreferences() {
  const queryClient = useQueryClient()
  const prefs = useQuery({
    queryKey: ["alerts", "preferences"],
    queryFn: async (): Promise<AlertPrefs> => (await API.get("/alerts/preferences")).data,
  })
  const [chosen, setChosen] = React.useState<string[] | null>(null)
  const [saving, setSaving] = React.useState(false)

  const current = chosen ?? (prefs.data?.kinds ?? []).filter((k) => k.whatsapp).map((k) => k.kind)
  const dirty = chosen !== null

  function toggle(kind: string) {
    setChosen((prev) => {
      const base = prev ?? current
      return base.includes(kind) ? base.filter((k) => k !== kind) : [...base, kind]
    })
  }

  async function save() {
    setSaving(true)
    try {
      await API.put("/alerts/preferences", { whatsapp_kinds: current })
      await queryClient.invalidateQueries({ queryKey: ["alerts", "preferences"] })
      setChosen(null)
      toast("Alert choices saved.")
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? "Could not save your alert choices.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="rounded-lg border border-border bg-card p-4">
      <h2 className="text-sm font-medium">Alerts on WhatsApp</h2>
      <p className="mt-1 font-mono text-[11px] text-muted-foreground">
        Pick what should reach you on WhatsApp. Everything shows in the dashboard either way.
      </p>

      {prefs.data && !prefs.data.owner_phone && (
        <p className="mt-3 rounded-md bg-need-soft p-2 text-sm text-need">
          Add your WhatsApp number in Restaurant settings, or these alerts can&apos;t reach you.
        </p>
      )}

      <ul className="mt-3 space-y-3">
        {(prefs.data?.kinds ?? []).map((k) => (
          <li key={k.kind} className="flex items-start gap-3">
            <input
              id={`alert-${k.kind}`}
              type="checkbox"
              className="mt-1 size-4 accent-foreground"
              checked={current.includes(k.kind)}
              onChange={() => toggle(k.kind)}
            />
            <label htmlFor={`alert-${k.kind}`} className="text-sm">
              <span className="block">{k.label}</span>
              <span className="block text-xs text-muted-foreground">{k.description}</span>
            </label>
          </li>
        ))}
      </ul>

      <div className="mt-4 flex justify-end">
        <Button size="sm" disabled={!dirty || saving} onClick={save}>
          {saving ? "Saving…" : "Save alert choices"}
        </Button>
      </div>
    </section>
  )
}
