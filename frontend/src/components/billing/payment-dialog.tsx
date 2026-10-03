"use client"

import * as React from "react"
import { useQueryClient } from "@tanstack/react-query"
import { CheckCircle2Icon, Loader2Icon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { usePlans } from "@/hooks/billing/use-subscription"
import { checkout, payInvoice, type PaymentResponse, type PlanOption } from "@/services/billing/billing.service"

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

/**
 * Runs one payment and walks through the stages: processing, then "Payment done" or a
 * failure the owner can retry. Used for a new plan and for paying an open invoice.
 */
function PaymentStages({
  stage,
  result,
  error,
  planName,
  onRetry,
  onDone,
}: {
  stage: Stage
  result: PaymentResponse | null
  error: string | null
  planName: string
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
    const until = dateLabel(result.subscription.current_period_end)
    return (
      <div className="flex flex-col items-center gap-3 py-6 text-center">
        <CheckCircle2Icon className="size-10 text-ok" />
        <p className="font-display text-[17px] font-semibold">Payment done</p>
        <p className="font-mono text-[15px] tabular-nums">{rupees(inv.amount_pkr)}</p>
        <p className="font-mono text-xs text-muted-foreground">{inv.invoice_id}</p>
        {until && (
          <p className="text-sm text-muted-foreground">
            Your {planName} plan is active until {until}.
          </p>
        )}
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

/** Pick a plan, then pay it. The subscription starts once the payment goes through. */
export function PlanPickerDialog({
  open,
  onOpenChange,
  currentPlanKey,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  currentPlanKey: string | null
}) {
  const plans = usePlans()
  const queryClient = useQueryClient()
  const [interval, setInterval] = React.useState<Interval>("month")
  const [selected, setSelected] = React.useState<string>("standard")
  const [stage, setStage] = React.useState<Stage>("pick")
  const [result, setResult] = React.useState<PaymentResponse | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  const chosen = plans.data?.find((p) => p.key === selected)

  async function pay() {
    setStage("processing")
    setError(null)
    try {
      setResult(await checkout(selected, interval))
      setStage("done")
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "The payment didn't go through.")
      setStage("failed")
    }
  }

  function close() {
    if (stage === "done") {
      queryClient.invalidateQueries({ queryKey: ["billing"] })
    }
    setStage("pick")
    setResult(null)
    setError(null)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={(o) => (stage === "processing" ? undefined : o ? onOpenChange(true) : close())}>
      <DialogContent className="sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle className="font-display">Choose a plan</DialogTitle>
          <DialogDescription className="flex items-center gap-2">
            <TestBadge />
          </DialogDescription>
        </DialogHeader>

        {stage === "pick" && (
          <div className="flex flex-col gap-4">
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

            <DialogFooter className="items-center sm:justify-between">
              <span className="font-mono text-sm tabular-nums">
                {chosen ? `Total ${rupees(priceFor(chosen, interval))}` : ""}
              </span>
              <Button onClick={pay} disabled={!chosen}>
                {chosen ? `Pay ${rupees(priceFor(chosen, interval))}` : "Pay"}
              </Button>
            </DialogFooter>
          </div>
        )}

        {stage !== "pick" && (
          <PaymentStages
            stage={stage}
            result={result}
            error={error}
            planName={chosen?.name ?? "chosen"}
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
}: {
  invoiceId: string
  amountPkr: number
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const queryClient = useQueryClient()
  const [stage, setStage] = React.useState<Stage>("processing")
  const [result, setResult] = React.useState<PaymentResponse | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (open) void run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  async function run() {
    setStage("processing")
    setError(null)
    try {
      setResult(await payInvoice(invoiceId))
      setStage("done")
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "The payment didn't go through.")
      setStage("failed")
    }
  }

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
          planName="current"
          onRetry={run}
          onDone={close}
        />
      </DialogContent>
    </Dialog>
  )
}
