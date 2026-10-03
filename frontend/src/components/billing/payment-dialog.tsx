"use client"

import * as React from "react"
import { useQueryClient } from "@tanstack/react-query"
import { CheckCircle2Icon, Loader2Icon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { usePlans } from "@/hooks/billing/use-subscription"
import {
  changePlan,
  checkout,
  payInvoice,
  type PaymentResponse,
  type PlanOption,
} from "@/services/billing/billing.service"

type Interval = "month" | "year"
type Stage = "pick" | "processing" | "done" | "failed"

function rupees(amount: number) {
  return `Rs ${amount.toLocaleString("en-US")}`
}

function dateLabel(iso: string | null | undefined) {
  if (!iso) return ""
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })
}

function priceFor(plan: PlanOption, interval: Interval) {
  return interval === "year" ? plan.price_yearly_pkr : plan.price_monthly_pkr
}

/** Shown on every payment screen while the dummy provider is active. Never claims a real charge. */
function TestBadge() {
  return (
    <Badge variant="outline" className="font-mono text-[11px] uppercase tracking-[0.08em]">
      Test payment, no money is charged
    </Badge>
  )
}

/** Processing, then "Payment done" or a failure the owner can retry. */
function PaymentStages({
  stage,
  result,
  error,
  successTitle,
  successNote,
  onRetry,
  onDone,
}: {
  stage: Stage
  result: PaymentResponse | null
  error: string | null
  successTitle: string
  successNote: string | null
  onRetry: () => void
  onDone: () => void
}) {
  if (stage === "processing") {
    return (
      <div className="flex flex-col items-center gap-3 py-8 text-center">
        <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
        <p className="text-sm">Processing payment…</p>
      </div>
    )
  }

  if (stage === "done" && result) {
    const inv = result.invoice
    return (
      <div className="flex flex-col items-center gap-3 py-6 text-center">
        <CheckCircle2Icon className="size-10 text-ok" />
        <p className="font-display text-[17px] font-semibold">{successTitle}</p>
        {inv && <p className="font-mono text-[15px] tabular-nums">{rupees(inv.amount_pkr)}</p>}
        {inv && <p className="font-mono text-xs text-muted-foreground">{inv.invoice_id}</p>}
        {successNote && <p className="text-sm text-muted-foreground">{successNote}</p>}
        <DialogFooter className="mt-2 w-full sm:justify-center">
          <Button onClick={onDone}>Done</Button>
        </DialogFooter>
      </div>
    )
  }

  if (stage === "failed") {
    return (
      <div className="flex flex-col items-center gap-3 py-6 text-center">
        <p className="text-sm text-need">{error ?? "The payment didn't go through."}</p>
        <p className="text-xs text-muted-foreground">Nothing was charged. Your invoice is still open.</p>
        <DialogFooter className="mt-2 w-full sm:justify-center">
          <Button variant="outline" onClick={onDone}>Close</Button>
          <Button onClick={onRetry}>Try again</Button>
        </DialogFooter>
      </div>
    )
  }

  return null
}

/**
 * Pick a plan, then pay it. "new" starts a subscription. "change" moves an active one:
 * an upgrade is charged now (prorated), a downgrade starts at the next renewal.
 */
export function PlanPickerDialog({
  open,
  onOpenChange,
  mode = "new",
  currentPlanKey,
  currentInterval = "month",
  periodEnd,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  mode?: "new" | "change"
  currentPlanKey: string | null
  currentInterval?: Interval
  periodEnd?: string | null
}) {
  const plans = usePlans()
  const queryClient = useQueryClient()
  const [interval, setInterval] = React.useState<Interval>(mode === "change" ? currentInterval : "month")
  const [selected, setSelected] = React.useState<string>("standard")
  const [stage, setStage] = React.useState<Stage>("pick")
  const [result, setResult] = React.useState<PaymentResponse | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [downgrade, setDowngrade] = React.useState(false)

  const chosen = plans.data?.find((p) => p.key === selected)
  const currentPlan = plans.data?.find((p) => p.key === currentPlanKey)
  const isUpgrade =
    mode === "change" && !!chosen && !!currentPlan && priceFor(chosen, interval) > priceFor(currentPlan, interval)
  const isChangeToSame = mode === "change" && selected === currentPlanKey

  async function pay() {
    setStage("processing")
    setError(null)
    setDowngrade(mode === "change" && !isUpgrade)
    try {
      const res = mode === "change" ? await changePlan(selected) : await checkout(selected, interval)
      setResult(res)
      setStage("done")
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "The payment didn't go through.")
      setStage("failed")
    }
  }

  function close() {
    if (stage === "done") queryClient.invalidateQueries({ queryKey: ["billing"] })
    setStage("pick")
    setResult(null)
    setError(null)
    onOpenChange(false)
  }

  let successTitle = "Payment done"
  let successNote: string | null = null
  if (stage === "done" && result) {
    if (!result.invoice) {
      successTitle = "Downgrade scheduled"
      successNote = `${chosen?.name ?? "The new"} plan starts on ${dateLabel(periodEnd) || "your next renewal"}. No payment today.`
    } else {
      successNote = `Your ${chosen?.name ?? ""} plan is active${mode === "change" ? " now" : ` until ${dateLabel(result.subscription.current_period_end)}`}.`
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => (stage === "processing" ? undefined : o ? onOpenChange(true) : close())}>
      <DialogContent className="sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle className="font-display">{mode === "change" ? "Change plan" : "Choose a plan"}</DialogTitle>
          <DialogDescription className="flex items-center gap-2">
            <TestBadge />
          </DialogDescription>
        </DialogHeader>

        {stage === "pick" && (
          <div className="flex flex-col gap-4">
            {mode === "new" && (
              <div className="inline-flex w-fit rounded-md border p-0.5 text-sm">
                {(["month", "year"] as Interval[]).map((i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => setInterval(i)}
                    className={`rounded px-3 py-1 ${interval === i ? "bg-foreground text-background" : "text-muted-foreground"}`}
                  >
                    {i === "month" ? "Monthly" : "Yearly (2 months free)"}
                  </button>
                ))}
              </div>
            )}

            <div className="grid gap-3 sm:grid-cols-3">
              {(plans.data ?? []).map((p) => (
                <button
                  key={p.key}
                  type="button"
                  onClick={() => setSelected(p.key)}
                  className={`flex flex-col gap-1 rounded-xl border bg-card p-3 text-left ${selected === p.key ? "border-foreground" : ""}`}
                >
                  <span className="flex items-center justify-between font-display font-semibold">
                    {p.name}
                    {currentPlanKey === p.key && <span className="text-xs text-muted-foreground">Current</span>}
                  </span>
                  <span className="font-mono text-[15px] tabular-nums">{rupees(priceFor(p, interval))}</span>
                  <span className="text-xs text-muted-foreground">
                    per {interval === "year" ? "year" : "month"} · {p.ai_conversations_per_month.toLocaleString()} AI chats
                  </span>
                </button>
              ))}
            </div>

            {mode === "change" && chosen && !isChangeToSame && (
              <p className="text-sm text-muted-foreground">
                {isUpgrade
                  ? "Upgrading starts now. You pay the difference for the rest of this period."
                  : `Downgrading starts on ${dateLabel(periodEnd) || "your next renewal"}. You keep your current plan until then.`}
              </p>
            )}

            <DialogFooter className="items-center sm:justify-between">
              <span className="font-mono text-sm tabular-nums">
                {chosen && !isChangeToSame ? `Total ${rupees(priceFor(chosen, interval))}` : ""}
              </span>
              <Button onClick={pay} disabled={!chosen || isChangeToSame}>
                {!chosen
                  ? "Pay"
                  : mode === "change" && !isUpgrade
                    ? "Schedule downgrade"
                    : `Pay ${rupees(priceFor(chosen, interval))}`}
              </Button>
            </DialogFooter>
          </div>
        )}

        {stage !== "pick" && (
          <PaymentStages
            stage={stage}
            result={result}
            error={error}
            successTitle={downgrade ? "Downgrade scheduled" : successTitle}
            successNote={successNote}
            onRetry={pay}
            onDone={close}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

/** Pays an invoice that is still open (for example after a failed payment). */
export function PayInvoiceDialog({
  invoiceId,
  amountPkr,
  open,
  onOpenChange,
  payFn,
}: {
  invoiceId: string
  amountPkr: number
  open: boolean
  onOpenChange: (open: boolean) => void
  payFn?: (id: string) => Promise<PaymentResponse>
}) {
  const queryClient = useQueryClient()
  const [stage, setStage] = React.useState<Stage>("processing")
  const [result, setResult] = React.useState<PaymentResponse | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  const run = React.useCallback(async () => {
    setStage("processing")
    setError(null)
    try {
      setResult(await (payFn ?? payInvoice)(invoiceId))
      setStage("done")
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "The payment didn't go through.")
      setStage("failed")
    }
  }, [invoiceId, payFn])

  React.useEffect(() => {
    if (open) void run()
  }, [open, run])

  function close() {
    if (stage === "done") queryClient.invalidateQueries({ queryKey: ["billing"] })
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={(o) => (stage === "processing" ? undefined : o ? onOpenChange(true) : close())}>
      <DialogContent className="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle className="font-display">Pay invoice</DialogTitle>
          <DialogDescription className="flex items-center gap-2">
            <TestBadge />
            <span className="font-mono text-xs tabular-nums">{rupees(amountPkr)}</span>
          </DialogDescription>
        </DialogHeader>
        <PaymentStages
          stage={stage}
          result={result}
          error={error}
          successTitle="Payment done"
          successNote={result ? "Your subscription is active." : null}
          onRetry={run}
          onDone={close}
        />
      </DialogContent>
    </Dialog>
  )
}
