"use client"

import * as React from "react"

import { PayInvoiceDialog, PlanPickerDialog } from "@/components/billing/payment-dialog"
import { Button } from "@/components/ui/button"
import { useInvoices, useSubscription } from "@/hooks/billing/use-subscription"
import { formatMoney } from "@/lib/currency"

/**
 * Shown above every dashboard page when the subscription needs attention: trial,
 * payment due, paused, or ended. Hidden while everything is fine.
 */
export function BillingBanner() {
  const sub = useSubscription()
  const invoices = useInvoices()
  const [pickerOpen, setPickerOpen] = React.useState(false)
  const [paying, setPaying] = React.useState(false)

  const d = sub.data
  if (!d) return null

  const used = d.usage.used
  const trialing = d.status === "trialing"
  const trialOver = trialing && (d.trial_days_left === 0 || used >= d.included_chats)
  const dueInvoice = (invoices.data ?? []).find((i) => i.status === "open" && i.purpose === "renewal")

  let message: React.ReactNode = null
  let tone: "need" | "muted" = "muted"
  let action: "choose" | "pay" | null = null

  if (trialOver) {
    message = "Your free trial has ended, so the agent has stopped replying to customers."
    tone = "need"
    action = "choose"
  } else if (trialing) {
    message = `${d.trial_days_left ?? 0} days left in your free trial.`
    action = "choose"
  } else if (d.status === "past_due") {
    message = "Payment is overdue. Your agent keeps replying for now, but it will pause if the invoice stays unpaid."
    tone = "need"
    action = "pay"
  } else if (d.status === "paused") {
    message = "Your agent is paused. Customers aren't being answered until you pay."
    tone = "need"
    action = "pay"
  } else if (d.status === "canceled") {
    message = "Your plan has ended, so the agent has stopped replying to customers."
    tone = "need"
    action = "choose"
  }

  if (!message) return null

  return (
    <div
      role="status"
      className={`flex flex-wrap items-center justify-between gap-3 px-4 py-2 text-sm ${
        tone === "need" ? "bg-need-soft text-need" : "bg-muted text-foreground"
      }`}
    >
      <span>{message}</span>
      {action === "choose" && (
        <Button size="sm" onClick={() => setPickerOpen(true)}>
          Choose a plan
        </Button>
      )}
      {action === "pay" && dueInvoice && (
        <Button size="sm" onClick={() => setPaying(true)}>
          Pay now · {formatMoney(dueInvoice.amount_pkr, "PKR")}
        </Button>
      )}

      <PlanPickerDialog open={pickerOpen} onOpenChange={setPickerOpen} mode="new" currentPlanKey={d.plan} />
      {paying && dueInvoice && (
        <PayInvoiceDialog
          invoiceId={dueInvoice.invoice_id}
          amountPkr={dueInvoice.amount_pkr}
          open
          onOpenChange={(o) => {
            if (!o) setPaying(false)
          }}
        />
      )}
    </div>
  )
}
