"use client"

import * as React from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { listPrintJobs, markPrinted, type PrintJob } from "@/services/staff/staff.service"

function money(n: number) {
  return Math.round(n).toLocaleString("en-US")
}

/** The bills waiting at the counter. Print opens the printer dialog; mark printed once the slip is out. */
export function CounterBills() {
  const queryClient = useQueryClient()
  const jobs = useQuery({ queryKey: ["counter", "print-jobs"], queryFn: listPrintJobs, refetchInterval: 4000, retry: false })
  const [printing, setPrinting] = React.useState<PrintJob | null>(null)

  const done = useMutation({
    mutationFn: (id: string) => markPrinted(id),
    onSuccess: () => {
      toast.success("Marked printed.")
      setPrinting(null)
      queryClient.invalidateQueries({ queryKey: ["counter", "print-jobs"] })
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
  if (list.length === 0 && !printing) return null

  return (
    <section className="grid gap-3 rounded-2xl border-2 border-foreground bg-card p-4">
      <h2 className="text-lg font-semibold">Bills to print ({list.length})</h2>
      {list.map((job) => (
        <div key={job.job_id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border p-3">
          <div>
            <p className="text-base font-semibold">Table {job.receipt?.table_no ?? "?"} · Rs {money(job.receipt?.total ?? 0)}</p>
            <p className="text-sm text-muted-foreground">{job.receipt?.customer_name ?? "No name"}</p>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={() => setPrinting(job)} className="min-h-12 rounded-xl bg-foreground px-4 text-base font-semibold text-background">
              Print
            </button>
            {printing?.job_id === job.job_id && (
              <button type="button" onClick={() => done.mutate(job.job_id)} disabled={done.isPending} className="min-h-12 rounded-xl border-2 border-border px-4 text-base">
                Printed
              </button>
            )}
          </div>
        </div>
      ))}

      {printing?.receipt && <Receipt job={printing} />}
    </section>
  )
}

/** The receipt, sized for a thermal printer. Shown only when printing. */
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
          <span>{money(i.amount)}</span>
        </div>
      ))}
      <div className="rule" />
      <div className="row" style={{ fontWeight: 700 }}>
        <span>TOTAL</span>
        <span>{money(r.total)}</span>
      </div>
      <div className="row"><span>Payment</span><span>{r.payment}</span></div>
      <div className="rule" />
      <div style={{ textAlign: "center", fontFamily: "monospace", fontSize: 12 }}>Thank you</div>
    </div>
  )
}
