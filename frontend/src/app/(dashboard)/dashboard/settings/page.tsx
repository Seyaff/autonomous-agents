"use client"

import * as React from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Progress } from "@/components/ui/progress"
import { LiveOnly } from "@/components/dashboard/live-only"
import { Badge } from "@/components/ui/badge"
import { WhatsAppConnectOptions } from "@/components/whatsapp/whatsapp-connect-options"
import { useQueryClient } from "@tanstack/react-query"
import { useTenantSettings } from "@/hooks/tenant/use-tenant-settings"
import { useUsage } from "@/hooks/billing/use-usage"
import { AlertPreferences } from "@/components/settings/alert-preferences"
import { USE_MOCKS } from "@/lib/mocks"
import type { TenantSettingsUpdate } from "@/services/tenant/tenant.service"

const FALLBACK_ZONES = ["UTC", "Asia/Karachi", "Asia/Dubai", "Europe/London", "America/New_York"]

function timezones(): string[] {
  const supported = (Intl as unknown as { supportedValuesOf?: (k: string) => string[] }).supportedValuesOf
  return supported ? supported("timeZone") : FALLBACK_ZONES
}

function errorText(err: unknown, fallback: string) {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback
}

export default function SettingsPage() {
  if (USE_MOCKS) return <LiveOnly title="Settings" />
  return <Settings />
}

function Settings() {
  const { tenant, update, toggleAgent } = useTenantSettings()
  const usage = useUsage()
  const zones = React.useMemo(() => timezones(), [])

  // Only what the owner has edited. Everything else shows the saved value.
  const [draft, setDraft] = React.useState<TenantSettingsUpdate>({})

  if (tenant.isLoading || !tenant.data) {
    return <p className="p-6 font-mono text-[12px] text-muted-foreground">Loading...</p>
  }

  const t = tenant.data
  const value = <K extends keyof TenantSettingsUpdate>(key: K, saved: TenantSettingsUpdate[K]) =>
    (draft[key] ?? saved ?? "") as string

  const dirty = Object.keys(draft).length > 0

  function set<K extends keyof TenantSettingsUpdate>(key: K, v: TenantSettingsUpdate[K]) {
    setDraft((d) => ({ ...d, [key]: v }))
  }

  function save(e: React.FormEvent) {
    e.preventDefault()
    update.mutate(draft, {
      onSuccess: () => {
        toast("Settings saved.")
        setDraft({})
      },
      onError: (err) => toast.error(errorText(err, "Could not save settings.")),
    })
  }

  function toggle(enabled: boolean) {
    toggleAgent.mutate(enabled, {
      onSuccess: () => toast(enabled ? "Agent is replying to customers." : "Agent paused. You will reply by hand."),
      onError: () => toast.error("Could not change the agent setting."),
    })
  }

  const u = usage.data
  const pct = u ? Math.min(100, Math.round((u.used / u.limit) * 100)) : 0

  return (
    <div className="flex flex-1 flex-col overflow-y-auto">
      <div className="shrink-0 border-b border-border bg-card px-4 py-2">
        <h1 className="text-sm font-medium">Settings</h1>
        <p className="font-mono text-[11px] text-muted-foreground">Restaurant details, the agent, and your plan</p>
      </div>

      <div className="grid gap-4 p-4 lg:grid-cols-[1fr_320px]">
        <form onSubmit={save} className="space-y-6 rounded-lg border border-border bg-card p-4">
          <section className="space-y-4">
            <h2 className="text-sm font-medium">Restaurant</h2>
            <Field id="s-name" label="Business name">
              <Input id="s-name" value={value("business_name", t.business_name)} onChange={(e) => set("business_name", e.target.value)} />
            </Field>
            <Field id="s-phone" label="Business phone">
              <Input id="s-phone" value={value("business_phone", t.business_phone ?? "")} onChange={(e) => set("business_phone", e.target.value)} />
            </Field>
            <Field id="s-address" label="Address">
              <Input id="s-address" value={value("address", t.address ?? "")} onChange={(e) => set("address", e.target.value)} />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field id="s-currency" label="Currency">
                <Input id="s-currency" maxLength={3} value={value("currency", t.currency)} onChange={(e) => set("currency", e.target.value.toUpperCase())} />
              </Field>
              <Field id="s-tz" label="Timezone">
                <select
                  id="s-tz"
                  value={value("timezone", t.timezone)}
                  onChange={(e) => set("timezone", e.target.value)}
                  className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"
                >
                  {zones.map((z) => (
                    <option key={z} value={z}>{z}</option>
                  ))}
                </select>
              </Field>
            </div>
          </section>

          <section className="space-y-4 border-t border-border pt-6">
            <h2 className="text-sm font-medium">Delivery</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field id="s-fee" label="Delivery fee">
                <Input
                  id="s-fee"
                  type="number"
                  min={0}
                  step="0.01"
                  value={value("flat_delivery_fee", t.delivery_settings.flat_delivery_fee ?? 0)}
                  onChange={(e) => set("flat_delivery_fee", Number(e.target.value))}
                />
              </Field>
              <Field id="s-prep" label="Prep time (minutes)">
                <Input
                  id="s-prep"
                  type="number"
                  min={1}
                  value={value("avg_prep_time_minutes", t.delivery_settings.avg_prep_time_minutes ?? 30)}
                  onChange={(e) => set("avg_prep_time_minutes", Number(e.target.value))}
                />
              </Field>
            </div>
          </section>

          <div className="flex items-center justify-end gap-2 border-t border-border pt-4">
            {dirty && (
              <Button type="button" variant="ghost" size="sm" onClick={() => setDraft({})}>
                Discard
              </Button>
            )}
            <Button type="submit" size="sm" disabled={!dirty || update.isPending}>
              {update.isPending ? "Saving..." : "Save changes"}
            </Button>
          </div>
        </form>

        <div className="space-y-4">
          <section className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-medium">WhatsApp</h2>
                <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                  {t.whatsapp_status === "connected" || t.whatsapp_connected
                    ? `Connected${t.display_phone_number ? ` · ${t.display_phone_number}` : ""}${t.verified_name ? ` · ${t.verified_name}` : ""}`
                    : "Not connected. Customers can't reach the agent yet."}
                </p>
              </div>
              <Badge variant={t.whatsapp_status === "error" ? "destructive" : "outline"}>
                {t.whatsapp_status === "error" ? "Needs attention" : t.whatsapp_connected ? "Live" : "Not connected"}
              </Badge>
            </div>
            {t.whatsapp_status === "error" && t.whatsapp_last_error && (
              <p className="mt-3 rounded-md bg-destructive/10 p-2 text-xs text-destructive">{t.whatsapp_last_error}</p>
            )}
            <div className="mt-3">
              <WhatsAppConnect />
            </div>
          </section>

          <section className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-medium">Customer agent</h2>
                <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                  {t.agent_enabled
                    ? "Replying to customers on WhatsApp."
                    : "Paused. Customers reach you in the inbox, and you reply by hand."}
                </p>
              </div>
              <Switch checked={t.agent_enabled} onCheckedChange={toggle} disabled={toggleAgent.isPending} aria-label="Customer agent" />
            </div>
            <p className="mt-3 font-mono text-[11px] text-muted-foreground">
              WhatsApp: {t.whatsapp_connected ? `connected${t.display_phone_number ? ` (${t.display_phone_number})` : ""}` : "not connected"}
            </p>
          </section>

          <AlertPreferences />

          {u && (
            <section className="rounded-lg border border-border bg-card p-4">
              <h2 className="text-sm font-medium">Plan · {u.plan_name}</h2>
              <p className="mt-1 font-mono text-[11px] text-muted-foreground">Usage for {u.period}</p>
              <div className="mt-3 space-y-2">
                <div className="flex justify-between text-sm">
                  <span>AI conversations</span>
                  <span className="font-mono">{u.used.toLocaleString()} / {u.limit.toLocaleString()}</span>
                </div>
                <Progress value={pct} />
                <p className="font-mono text-[11px] text-muted-foreground">
                  {u.ai_messages.toLocaleString()} replies · {u.tokens_used.toLocaleString()} tokens
                </p>
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}

function Field({ id, label, children }: { id: string; label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  )
}


function WhatsAppConnect() {
  const queryClient = useQueryClient()
  return (
    <WhatsAppConnectOptions
      next="/dashboard/settings"
      onSuccess={() => {
        toast("WhatsApp connected.")
        queryClient.invalidateQueries({ queryKey: ["tenant", "settings"] })
      }}
      onError={(message) => toast.error(message)}
    />
  )
}
