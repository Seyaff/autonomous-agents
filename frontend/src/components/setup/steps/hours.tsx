"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { XIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { DialogDescription, DialogFooter, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useAuth } from "@/components/providers/auth-provider"
import { useSetupState } from "@/hooks/setup/use-setup-state"
import { useSetupStep } from "@/hooks/setup/use-setup-step"
import {
  updateRestaurant,
  type DayHoursPayload,
  type PaymentMethod,
} from "@/services/setup/setup.service"
import { StepError, errorDetail } from "@/components/setup/steps/common"

const DAYS = [
  { key: "mon", label: "Monday" },
  { key: "tue", label: "Tuesday" },
  { key: "wed", label: "Wednesday" },
  { key: "thu", label: "Thursday" },
  { key: "fri", label: "Friday" },
  { key: "sat", label: "Saturday" },
  { key: "sun", label: "Sunday" },
] as const

const PREP_OPTIONS = [20, 30, 35, 45, 60, 90]

const PAYMENTS: { value: PaymentMethod; label: string }[] = [
  { value: "cash_on_delivery", label: "Cash on delivery" },
  { value: "card_on_delivery", label: "Card on delivery" },
  { value: "bank_transfer", label: "Bank transfer" },
]

type Tab = "hours" | "delivery"

/** Reads saved hours in either format: the current one (mon, open, close) or
 * the older one (Monday, open_time, close_time, is_closed). */
function readHours(raw: Array<Record<string, unknown>> | undefined): DayHoursPayload[] {
  return DAYS.map(({ key }) => {
    const entry = (raw ?? []).find((h) => String(h.day ?? "").slice(0, 3).toLowerCase() === key)
    return {
      day: key,
      open: String(entry?.open ?? entry?.open_time ?? "12:00"),
      close: String(entry?.close ?? entry?.close_time ?? "23:30"),
      closed: Boolean(entry?.closed ?? entry?.is_closed ?? false),
    }
  })
}

export function HoursStep() {
  const router = useRouter()
  const { activeTenantId } = useAuth()
  const setup = useSetupState({ enabled: !!activeTenantId })
  const { complete } = useSetupStep()
  const saved = setup.tenant

  const [tab, setTab] = React.useState<Tab>("hours")
  const [hours, setHours] = React.useState<DayHoursPayload[] | null>(null)
  const [fee, setFee] = React.useState<number | null>(null)
  const [minOrder, setMinOrder] = React.useState<number | null>(null)
  const [prep, setPrep] = React.useState<number | null>(null)
  const [areas, setAreas] = React.useState<string[] | null>(null)
  const [areaDraft, setAreaDraft] = React.useState("")
  const [payments, setPayments] = React.useState<PaymentMethod[] | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [saving, setSaving] = React.useState(false)

  const rows = hours ?? readHours(saved?.operating_hours)
  const shownFee = fee ?? saved?.delivery_settings?.flat_delivery_fee ?? 0
  const shownMin = minOrder ?? saved?.min_order_amount ?? 0
  const shownPrep = prep ?? saved?.delivery_settings?.avg_prep_time_minutes ?? 30
  const shownAreas = areas ?? saved?.delivery_areas ?? []
  const shownPayments = (payments ?? (saved?.payment_methods as PaymentMethod[] | undefined) ?? ["cash_on_delivery"])
  const deliveryOn = (saved?.order_types ?? []).includes("delivery")
  const currency = saved?.currency ?? "USD"

  const paymentError = shownPayments.length === 0 ? "Pick at least one payment method." : null
  const areaError = deliveryOn && shownAreas.length === 0 ? "Add at least one delivery area." : null

  function updateRow(index: number, patch: Partial<DayHoursPayload>) {
    setHours(rows.map((r, i) => (i === index ? { ...r, ...patch } : r)))
  }

  function addArea(value: string) {
    const clean = value.trim()
    if (!clean) return
    setAreas([...shownAreas, clean].slice(0, 50))
    setAreaDraft("")
  }

  function removeArea(index: number) {
    setAreas(shownAreas.filter((_, i) => i !== index))
  }

  function togglePayment(value: PaymentMethod, on: boolean) {
    setPayments(on ? [...shownPayments, value] : shownPayments.filter((p) => p !== value))
  }

  async function save() {
    if (saving) return
    if (paymentError || areaError) {
      // Show the problem inline on the tab that has it, once.
      setTab("delivery")
      return
    }
    setSaving(true)
    setError(null)
    try {
      await updateRestaurant({
        operating_hours: rows,
        flat_delivery_fee: shownFee,
        min_order_amount: shownMin,
        avg_prep_time_minutes: shownPrep,
        delivery_areas: shownAreas,
        payment_methods: shownPayments,
      })
      await complete.mutateAsync({ step: "hours", action: "complete" })
      router.push("/setup/agent")
    } catch (err) {
      setError(errorDetail(err, "Could not save hours and delivery. Try again."))
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <div className="space-y-1.5">
        <DialogTitle className="font-heading text-lg">Hours and delivery</DialogTitle>
        <DialogDescription>When you&apos;re open, and what delivery looks like.</DialogDescription>
      </div>

      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
        <TabsList>
          <TabsTrigger value="hours">Opening hours</TabsTrigger>
          <TabsTrigger value="delivery">
            Delivery &amp; payment
            {(paymentError || areaError) && <span className="ml-1.5 size-1.5 rounded-full bg-destructive" />}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="hours" className="space-y-3 pt-2">
          {rows.map((row, i) => (
            <div key={row.day} className="grid grid-cols-[1fr_auto] items-center gap-3 sm:grid-cols-[120px_auto_1fr_1fr]">
              <div className="flex items-center gap-2">
                <Switch
                  checked={!row.closed}
                  onCheckedChange={(on: boolean) => updateRow(i, { closed: !on })}
                  aria-label={`${DAYS[i].label} open`}
                />
                <span className="text-sm">{DAYS[i].label}</span>
              </div>
              <div className="hidden sm:block" />
              <Input
                type="time"
                value={row.open}
                disabled={row.closed}
                onChange={(e) => updateRow(i, { open: e.target.value })}
                aria-label={`${DAYS[i].label} opens`}
              />
              <Input
                type="time"
                value={row.close}
                disabled={row.closed}
                onChange={(e) => updateRow(i, { close: e.target.value })}
                aria-label={`${DAYS[i].label} closes`}
              />
            </div>
          ))}
          <p className="font-mono text-[11px] text-muted-foreground">
            Closing after midnight counts toward the same day.
          </p>
        </TabsContent>

        <TabsContent value="delivery" className="space-y-5 pt-2">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="h-fee">Delivery fee</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="h-fee"
                  type="number"
                  min={0}
                  step="0.01"
                  value={shownFee}
                  onChange={(e) => setFee(Number(e.target.value))}
                />
                <Badge variant="outline">{currency}</Badge>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="h-min">Minimum order</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="h-min"
                  type="number"
                  min={0}
                  step="1"
                  value={shownMin}
                  onChange={(e) => setMinOrder(Number(e.target.value))}
                />
                <Badge variant="outline">{currency}</Badge>
              </div>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="h-prep">Usual delivery time</Label>
            <select
              id="h-prep"
              value={shownPrep}
              onChange={(e) => setPrep(Number(e.target.value))}
              className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm sm:w-56"
            >
              {PREP_OPTIONS.map((m) => (
                <option key={m} value={m}>{m} minutes</option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="h-area">Delivery areas</Label>
            <div className="flex flex-wrap gap-1.5">
              {shownAreas.map((area, i) => (
                <Badge key={`${area}-${i}`} variant="secondary" className="gap-1 pr-1">
                  {area}
                  <button
                    type="button"
                    onClick={() => removeArea(i)}
                    className="rounded-sm p-0.5 hover:bg-muted"
                    aria-label={`Remove ${area}`}
                  >
                    <XIcon className="size-3" />
                  </button>
                </Badge>
              ))}
            </div>
            <Input
              id="h-area"
              value={areaDraft}
              placeholder="Type an area and press Enter"
              onChange={(e) => setAreaDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault()
                  addArea(areaDraft)
                } else if (e.key === "Backspace" && areaDraft === "" && shownAreas.length > 0) {
                  removeArea(shownAreas.length - 1)
                }
              }}
            />
            {areaError && <p className="text-xs text-destructive">{areaError}</p>}
          </div>

          <fieldset className="space-y-2">
            <legend className="mb-1.5 text-sm font-medium">Payment methods</legend>
            <div className="grid gap-2 sm:grid-cols-3">
              {PAYMENTS.map((p) => {
                const checked = shownPayments.includes(p.value)
                return (
                  <label
                    key={p.value}
                    className={`flex cursor-pointer items-center gap-2 rounded-lg border p-3 text-sm ${
                      checked ? "border-foreground bg-muted" : "border-border"
                    }`}
                  >
                    <Checkbox
                      checked={checked}
                      onCheckedChange={(on: boolean) => togglePayment(p.value, on)}
                      aria-label={p.label}
                    />
                    {p.label}
                  </label>
                )
              })}
            </div>
            {paymentError && <p className="text-xs text-destructive">{paymentError}</p>}
          </fieldset>
        </TabsContent>
      </Tabs>

      <StepError message={error} />

      <DialogFooter>
        <Button variant="outline" onClick={() => router.push("/setup/menu")} disabled={saving}>
          Back
        </Button>
        <Button onClick={save} disabled={saving}>
          {saving ? "Saving..." : "Continue"}
        </Button>
      </DialogFooter>
    </>
  )
}
