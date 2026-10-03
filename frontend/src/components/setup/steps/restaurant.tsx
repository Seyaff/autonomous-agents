"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { useQueryClient } from "@tanstack/react-query"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { DialogDescription, DialogFooter, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useAuth } from "@/components/providers/auth-provider"
import { useSetupState } from "@/hooks/setup/use-setup-state"
import { useSetupStep } from "@/hooks/setup/use-setup-step"
import {
  createRestaurant,
  updateRestaurant,
  type CountryCode,
  type OrderType,
} from "@/services/setup/setup.service"
import { COUNTRY_LOCALE, StepError, errorDetail } from "@/components/setup/steps/common"

const ORDER_TYPES: { value: OrderType; label: string; hint: string }[] = [
  { value: "delivery", label: "Delivery", hint: "Riders bring it to the door" },
  { value: "takeaway", label: "Takeaway", hint: "Customer picks it up" },
  { value: "dine_in", label: "Dine-in", hint: "Table orders" },
]

export function RestaurantStep() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const { activeTenantId } = useAuth()
  const setup = useSetupState({ enabled: !!activeTenantId })
  const { complete } = useSetupStep()

  const existing = setup.tenant
  const [name, setName] = React.useState<string | null>(null)
  const [country, setCountry] = React.useState<CountryCode>("PK")
  const [city, setCity] = React.useState("")
  const [orderTypes, setOrderTypes] = React.useState<OrderType[] | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [saving, setSaving] = React.useState(false)

  // Coming back to this step after the restaurant exists: show what was saved.
  const shownName = name ?? existing?.business_name ?? ""
  const shownTypes: OrderType[] = orderTypes ?? ((existing?.order_types as OrderType[] | undefined) ?? ["delivery", "takeaway"])
  const locale = COUNTRY_LOCALE[country]
  const valid = shownName.trim().length >= 2 && shownTypes.length > 0

  function toggleType(type: OrderType, on: boolean) {
    setOrderTypes(on ? [...shownTypes, type] : shownTypes.filter((t) => t !== type))
  }

  async function save() {
    if (!valid || saving) return
    setSaving(true)
    setError(null)
    try {
      if (!activeTenantId) {
        await createRestaurant({
          business_name: shownName.trim(),
          country,
          city: city.trim() || undefined,
          order_types: shownTypes,
        })
        // The owner now has a restaurant. Reload the user so the gate sees it.
        await queryClient.invalidateQueries({ queryKey: ["me"] })
      } else {
        await updateRestaurant({ business_name: shownName.trim(), order_types: shownTypes })
        await complete.mutateAsync({ step: "restaurant", action: "complete" })
      }
      router.push("/setup/menu")
    } catch (err) {
      setError(errorDetail(err, "Could not save the restaurant. Try again."))
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <div className="space-y-1.5">
        <DialogTitle className="font-heading text-lg">Restaurant details</DialogTitle>
        <DialogDescription>The name your customers see on WhatsApp, and where you are.</DialogDescription>
      </div>

      <div className="grid gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="r-name">Restaurant name</Label>
          <Input
            id="r-name"
            value={shownName}
            onChange={(e) => setName(e.target.value)}
            placeholder="Da Pakhtun Dera"
            disabled={saving}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="r-country">Country</Label>
            <select
              id="r-country"
              value={country}
              onChange={(e) => setCountry(e.target.value as CountryCode)}
              disabled={!!activeTenantId || saving}
              className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm disabled:opacity-60"
            >
              {(Object.keys(COUNTRY_LOCALE) as CountryCode[]).map((code) => (
                <option key={code} value={code}>{COUNTRY_LOCALE[code].label}</option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="r-city">City</Label>
            <Input
              id="r-city"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              placeholder="Lahore"
              disabled={!!activeTenantId || saving}
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 font-mono text-[12px] text-muted-foreground">
          <span>Currency</span>
          <Badge variant="outline">{locale.currency}</Badge>
          <span>Timezone</span>
          <Badge variant="outline">{locale.timezone}</Badge>
          <span className="text-[11px]">set from the country</span>
        </div>

        <fieldset className="space-y-2">
          <legend className="mb-1.5 text-sm font-medium">How do customers order?</legend>
          <div className="grid gap-2 sm:grid-cols-3">
            {ORDER_TYPES.map((type) => {
              const checked = shownTypes.includes(type.value)
              return (
                <label
                  key={type.value}
                  className={`flex cursor-pointer items-start gap-2 rounded-lg border p-3 ${
                    checked ? "border-foreground bg-muted" : "border-border"
                  }`}
                >
                  <Checkbox
                    checked={checked}
                    onCheckedChange={(on: boolean) => toggleType(type.value, on)}
                    disabled={saving}
                    aria-label={type.label}
                  />
                  <span className="space-y-0.5">
                    <span className="block text-sm font-medium">{type.label}</span>
                    <span className="block text-xs text-muted-foreground">{type.hint}</span>
                  </span>
                </label>
              )
            })}
          </div>
          {shownTypes.length === 0 && (
            <p className="text-xs text-destructive">Pick at least one way customers can order.</p>
          )}
        </fieldset>
      </div>

      <StepError message={error} />

      <DialogFooter>
        <Button onClick={save} disabled={!valid || saving}>
          {saving ? "Saving..." : "Continue"}
        </Button>
      </DialogFooter>
    </>
  )
}
