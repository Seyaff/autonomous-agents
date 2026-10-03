"use client"

import * as React from "react"
import { useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { PayInvoiceDialog, PlanPickerDialog } from "@/components/billing/payment-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { usePlans, useInvoices, useSubscription } from "@/hooks/billing/use-subscription"
import { formatMoney } from "@/lib/currency"
import {
  cancelSubscription,
  resumeSubscription,
  type Invoice,
  type SubscriptionResponse,
} from "@/services/billing/billing.service"

const STATUS_LABEL: Record<SubscriptionResponse["status"], string> = {
  trialing: "Free trial",
  active: "Active",
  past_due: "Payment due",
  paused: "Paused",
  canceled: "Canceled",
}

function when(iso: string | null) {
  if (!iso) return "—"
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })
}

/** Plan, trial, AI chat usage, plan changes, cancellation and invoices. */
export default function BillingPage() {
  const queryClient = useQueryClient()
  const sub = useSubscription()
  const plans = usePlans()
  const invoices = useInvoices()
  const [pickerOpen, setPickerOpen] = React.useState(false)
  const [changeOpen, setChangeOpen] = React.useState(false)
  const [confirmCancel, setConfirmCancel] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [payingInvoice, setPayingInvoice] = React.useState<Invoice | null>(null)

  if (sub.isError) {
    return (
      <div className="flex flex-col items-start gap-3 rounded-xl border bg-card p-4">
        <p className="text-sm text-need">We couldn&apos;t load your plan. Check your connection and try again.</p>
        <Button variant="outline" onClick={() => sub.refetch()} disabled={sub.isFetching}>
          Try again
        </Button>
      </div>
    )
  }

  if (!sub.data) {
    return <p className="text-sm text-muted-foreground">Loading your plan…</p>
  }

  const d = sub.data
  const used = d.usage.used
  const limit = d.included_chats || 1
  const percent = Math.min(100, Math.round((used / limit) * 100))
  const trialing = d.status === "trialing"
  // Same rule as the backend gate: the trial ends at its date or at its chat cap.
  const trialOver = trialing && (d.trial_days_left === 0 || used >= d.included_chats)
  const active = d.status === "active"
  const canChoose = !active
  const openInvoices = (invoices.data ?? []).filter((i) => i.status === "open")
  const paidInvoices = (invoices.data ?? []).filter((i) => i.status === "paid")

  async function runSubscriptionAction(action: () => Promise<unknown>, message: string) {
    setBusy(true)
    try {
      await action()
      await queryClient.invalidateQueries({ queryKey: ["billing"] })
      toast.success(message)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? "Something went wrong. Try again.")
    } finally {
      setBusy(false)
      setConfirmCancel(false)
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-[640px] flex-col gap-6">
      <header>
        <h1 className="font-display text-[22px] font-semibold">Billing</h1>
        <p className="text-sm text-muted-foreground">Your plan, trial and AI chat usage.</p>
      </header>

      <section className="flex flex-col gap-3 rounded-xl border bg-card p-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-display text-[15px] font-semibold">Your plan</h2>
          <Badge variant="outline">{STATUS_LABEL[d.status]}</Badge>
        </div>
        <p className="text-[15px]">
          <span className="font-semibold">{d.plan_name}</span>
          {!trialing && (
            <span className="text-muted-foreground">
              {" "}· {formatMoney(d.price_pkr, "PKR")} per {d.interval === "year" ? "year" : "month"}
            </span>
          )}
        </p>
        {trialing && trialOver ? (
          <p className="text-sm text-need">
            Your free trial has ended, so the agent has stopped replying to customers. Choose a plan to start again.
          </p>
        ) : trialing ? (
          <p className="text-sm text-muted-foreground">
            {d.trial_days_left !== null ? `${d.trial_days_left} days left in your free trial.` : "Free trial."} No payment needed yet.
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">
            Current period: {when(d.current_period_start)} to {when(d.current_period_end)}
          </p>
        )}

        {d.cancel_at_period_end && (
          <div className="flex items-center justify-between gap-3 rounded-md bg-need-soft p-3 text-sm text-need">
            <span>Your plan ends on {when(d.current_period_end)}.</span>
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => runSubscriptionAction(resumeSubscription, "Your plan will keep renewing.")}
            >
              Keep my plan
            </Button>
          </div>
        )}
        {d.pending_plan && (
          <p className="text-sm text-muted-foreground">
            Changes to {d.pending_plan_name} on {when(d.current_period_end)}.
          </p>
        )}

        <div className="flex flex-wrap gap-2">
          {canChoose && <Button onClick={() => setPickerOpen(true)}>Choose a plan</Button>}
          {active && !d.cancel_at_period_end && (
            <>
              <Button variant="outline" onClick={() => setChangeOpen(true)}>Change plan</Button>
              {confirmCancel ? (
                <>
                  <Button variant="destructive" disabled={busy} onClick={() => runSubscriptionAction(cancelSubscription, "Your plan will end at the end of this period.")}>
                    Yes, cancel at period end
                  </Button>
                  <Button variant="ghost" onClick={() => setConfirmCancel(false)}>Keep plan</Button>
                </>
              ) : (
                <Button variant="ghost" onClick={() => setConfirmCancel(true)}>Cancel plan</Button>
              )}
            </>
          )}
        </div>
      </section>

      <section className="flex flex-col gap-3 rounded-xl border bg-card p-4">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="font-display text-[15px] font-semibold">AI chats this month</h2>
          <span className="font-mono text-sm tabular-nums">
            {used.toLocaleString()} / {d.included_chats.toLocaleString()}
          </span>
        </div>
        <div className="h-[5px] w-full overflow-hidden rounded-full bg-muted" aria-label="AI chats used">
          <div className="h-full rounded-full bg-foreground" style={{ width: `${percent}%` }} />
        </div>
        <p className="text-sm text-muted-foreground">
          {trialing
            ? `Free trial: up to ${d.included_chats} AI chats. Extra chats are charged after you choose a plan.`
            : `Extra chats are ${formatMoney(d.extra_chat_pkr, "PKR")} each, added to your next invoice.`}
        </p>
        {!trialing && d.next_invoice_date && !d.cancel_at_period_end && (
          <p className="text-sm">
            Next invoice on {when(d.next_invoice_date)}, about{" "}
            <span className="font-mono tabular-nums">{formatMoney(d.next_invoice_pkr, "PKR")}</span>.
          </p>
        )}
        <p className="text-xs text-muted-foreground">
          Your WhatsApp fee this month (paid to Meta, not Siyaf): about{" "}
          <span className="font-mono tabular-nums">{formatMoney(d.meta_fee_pkr, "PKR")}</span>.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="font-display text-[15px] font-semibold">Plans</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {(plans.data ?? []).map((p) => {
            const current = p.key === d.plan
            return (
              <div
                key={p.key}
                className={`flex flex-col gap-2 rounded-xl border bg-card p-4 ${current ? "border-foreground" : ""}`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-display font-semibold">{p.name}</span>
                  {current && <Badge variant="outline">Current</Badge>}
                </div>
                <span className="font-mono text-[17px] tabular-nums">
                  {formatMoney(p.price_monthly_pkr, "PKR")}
                  <span className="text-xs text-muted-foreground"> / month</span>
                </span>
                <span className="text-xs text-muted-foreground">
                  or {formatMoney(p.price_yearly_pkr, "PKR")} / year (2 months free)
                </span>
                <span className="text-sm">{p.ai_conversations_per_month.toLocaleString()} AI chats included</span>
                <span className="text-xs text-muted-foreground">Extra chats {formatMoney(p.extra_chat_pkr, "PKR")} each</span>
              </div>
            )
          })}
        </div>
        <p className="text-xs text-muted-foreground">
          WhatsApp fees are billed by Meta to your business directly, not by Siyaf.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="font-display text-[15px] font-semibold">Invoices</h2>
        {openInvoices.map((inv) => (
          <div key={inv.invoice_id} className="flex items-center justify-between gap-3 rounded-xl border bg-card p-3">
            <div className="flex flex-col">
              <span className="font-mono text-sm">{inv.invoice_id}</span>
              <span className="text-xs text-muted-foreground">Due {when(inv.due_at)}</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="font-mono text-sm tabular-nums">{formatMoney(inv.amount_pkr, "PKR")}</span>
              <Button size="sm" onClick={() => setPayingInvoice(inv)}>Pay</Button>
            </div>
          </div>
        ))}
        {paidInvoices.map((inv) => (
          <div key={inv.invoice_id} className="flex items-center justify-between gap-3 rounded-xl border bg-card p-3">
            <div className="flex flex-col">
              <span className="font-mono text-sm">{inv.invoice_id}</span>
              <span className="text-xs text-muted-foreground">Paid {when(inv.paid_at)}</span>
            </div>
            <span className="font-mono text-sm tabular-nums">{formatMoney(inv.amount_pkr, "PKR")}</span>
          </div>
        ))}
        {(invoices.data ?? []).length === 0 && (
          <p className="rounded-md border border-dashed p-3 font-mono text-xs text-muted-foreground">
            No invoices yet. They appear here once you choose a plan.
          </p>
        )}
      </section>

      <PlanPickerDialog
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        mode="new"
        currentPlanKey={d.plan}
      />
      <PlanPickerDialog
        open={changeOpen}
        onOpenChange={setChangeOpen}
        mode="change"
        currentPlanKey={d.plan}
        currentInterval={d.interval}
        periodEnd={d.current_period_end}
      />
      {payingInvoice && (
        <PayInvoiceDialog
          invoiceId={payingInvoice.invoice_id}
          amountPkr={payingInvoice.amount_pkr}
          open
          onOpenChange={(o) => {
            if (!o) setPayingInvoice(null)
          }}
        />
      )}
    </div>
  )
}
