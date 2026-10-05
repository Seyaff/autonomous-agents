"use client"

import * as React from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { listPrintJobs, markPrinted, type PrintJob } from "@/services/staff/staff.service"

function money(n: number) {
  return `Rs ${Math.round(n).toLocaleString("en-US")}`
}

/** Bills waiting to be printed. Print sends the bill to the thermal printer; Printed takes it off the list. */
export function CounterBills() {
  const queryClient = useQueryClient()
  const jobs = useQuery({ queryKey: ["counter", "print-jobs"], queryFn: listPrintJobs, refetchInterval: 4000, retry: false })
  const [printing, setPrinting] = React.useState<PrintJob | null>(null)

  const done = useMutation({
    mutationFn: (id: string) => markPrinted(id),
    onSuccess: () => {
      toast.success("Bill marked printed.")
      setPrinting(null)
      queryClient.invalidateQueries({ queryKey: ["counter"] })
    },
    onError: (err) => toast.error((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Could not update."),
  })

  // Open the printer dialog once the receipt is on the page.
  React.useEffect(() => {
    if (!printing) return
    const timer = window.setTimeout(() => window.print(), 100)
    return () => window.clearTimeout(timer)
  }, [printing])

  const list = jobs.data ?? []

  return (
    <section className="grid gap-3 rounded-2xl border-2 border-foreground bg-card p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">To print</h2>
        <span className="text-base text-muted-foreground">{list.length} waiting</span>
      </div>

      {jobs.isPending && <p className="text-base text-muted-foreground">Loading…</p>}
      {jobs.data && list.length === 0 && <p className="text-base text-muted-foreground">Nothing waiting to print.</p>}

      {list.map((job) => {
        const r = job.receipt
        return (
          <article key={job.job_id} className="grid gap-2 rounded-xl border-2 border-border p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="text-2xl font-bold">Table {r?.table_no ?? "?"}</span>
              <span className="text-base">{r?.customer_name ?? "No name"}</span>
            </div>
            <ul className="grid gap-1 text-base">
              {r?.items.map((i, idx) => (
                <li key={idx} className="flex justify-between gap-3">
                  <span>{i.qty} × {i.name}</span>
                  <span className="font-mono">{money(i.amount)}</span>
                </li>
              ))}
            </ul>
            <div className="flex items-center justify-between border-t border-border pt-2">
              <span className="text-base font-semibold">Total {money(r?.total ?? 0)}</span>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setPrinting(job)}
                  className="min-h-14 rounded-xl bg-foreground px-5 text-lg font-semibold text-background"
                >
                  Print
                </button>
                {printing?.job_id === job.job_id && (
                  <button
                    type="button"
                    onClick={() => done.mutate(job.job_id)}
                    disabled={done.isPending}
                    className="min-h-14 rounded-xl border-2 border-border px-5 text-lg"
                  >
                    Printed
                  </button>
                )}
              </div>
            </div>
          </article>
        )
      })}

      {printing?.receipt && <Receipt job={printing} />}
    </section>
  )
}

/** The receipt, sized for a thermal printer. Shown only while printing. */
function Receipt({ job }: { job: PrintJob }) {
  const r = job.receipt!
  return (
    <div className="print-only">
      <style>{`
        .print-only { display: none; }
        @media print {
          body * { visibility: hidden; }
          .print-only, .print-only * { visibility: visible; }
          .print-only { display: block; position: absolute; left: 0; top: 0; width: 72mm; color: #000; background: #fff; }
          @page { size: 80mm auto; margin: 3mm; }
        }
        .print-only .rule { border-top: 1px dashed #000; margin: 6px 0; }
        .print-only .row { display: flex; justify-content: space-between; font-family: monospace; font-size: 12px; }
      `}</style>
      <div style={{ textAlign: "center", fontFamily: "monospace", fontSize: 13 }}>
        <strong>{r.restaurant}</strong><br />
        Table {r.table_no} · Waiter {r.waiter}
        {r.customer_name && <><br />{r.customer_name}</>}
        {r.customer_phone && <><br />{r.customer_phone}</>}
      </div>
      <div className="rule" />
      {r.items.map((i, idx) => (
        <div key={idx} className="row">
          <span>{i.qty} x {i.name}</span>
          <span>{Math.round(i.amount).toLocaleString("en-US")}</span>
        </div>
      ))}
      <div className="rule" />
      <div className="row" style={{ fontWeight: 700 }}>
        <span>TOTAL</span>
        <span>{Math.round(r.total).toLocaleString("en-US")}</span>
      </div>
      <div className="row"><span>Payment</span><span>{r.payment}</span></div>
      <div className="rule" />
      <div style={{ textAlign: "center", fontFamily: "monospace", fontSize: 12 }}>Thank you</div>
    </div>
  )
}
