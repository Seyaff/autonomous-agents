"use client"

import * as React from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { LiveOnly } from "@/components/dashboard/live-only"
import { CampaignComposer } from "@/components/campaigns/campaign-composer"
import { useCampaign, useCampaignActions, useCampaigns } from "@/hooks/campaigns/use-campaigns"
import { USE_MOCKS } from "@/lib/mocks"
import { cn } from "@/lib/utils"
import type { Campaign } from "@/services/campaigns/campaigns.service"

const STATUS: Record<Campaign["status"], { label: string; className: string }> = {
  sending: { label: "Sending", className: "bg-ai-soft text-ai" },
  done: { label: "Sent", className: "bg-ok-soft text-ok" },
  paused: { label: "Paused", className: "bg-need-soft text-need" },
  failed: { label: "Failed", className: "bg-need-soft text-need" },
}

function errorText(err: unknown, fallback: string) {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback
}

function pct(part: number, whole: number) {
  return whole ? Math.round((part / whole) * 100) : 0
}

export default function CampaignsPage() {
  if (USE_MOCKS) return <LiveOnly title="Campaigns" />
  return <Campaigns />
}

function Campaigns() {
  const list = useCampaigns()
  const [composerOpen, setComposerOpen] = React.useState(false)
  const [openId, setOpenId] = React.useState<string | null>(null)
  const campaigns = list.data?.campaigns ?? []

  return (
    <div className="flex flex-1 flex-col overflow-y-auto">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border bg-card px-4 py-2">
        <div>
          <h1 className="text-sm font-medium">Campaigns</h1>
          <p className="font-mono text-[11px] text-muted-foreground">Send an approved template to many customers at once</p>
        </div>
        <Button size="sm" onClick={() => setComposerOpen(true)}>New campaign</Button>
      </div>

      <div className="p-4">
        {list.isLoading ? (
          <p className="font-mono text-[12px] text-muted-foreground">Loading...</p>
        ) : campaigns.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-6 text-center">
            <p className="text-sm">No campaigns yet.</p>
            <p className="mt-1 font-mono text-[12px] text-muted-foreground">
              Write a marketing template, wait for Meta to approve it, then send it here.
            </p>
          </div>
        ) : (
          <ul className="space-y-2">
            {campaigns.map((c) => (
              <CampaignRow key={c.campaign_id} campaign={c} open={openId === c.campaign_id}
                onToggle={() => setOpenId(openId === c.campaign_id ? null : c.campaign_id)} />
            ))}
          </ul>
        )}
      </div>

      <CampaignComposer open={composerOpen} onOpenChange={setComposerOpen} />
    </div>
  )
}

function Stat({ label, value, sub }: { label: string; value: number; sub?: string }) {
  return (
    <div>
      <p className="font-mono text-[11px] text-muted-foreground">{label}</p>
      <p className="text-sm font-medium tabular-nums">
        {value}
        {sub && <span className="ml-1 font-mono text-[11px] text-muted-foreground">{sub}</span>}
      </p>
    </div>
  )
}

function CampaignRow({ campaign: c, open, onToggle }: { campaign: Campaign; open: boolean; onToggle: () => void }) {
  const { resume } = useCampaignActions()
  const detail = useCampaign(open ? c.campaign_id : null)
  const done = c.counts.sent + c.counts.failed
  const look = STATUS[c.status]
  const canResume = c.status === "paused" || (c.status === "sending" && c.stalled)

  function doResume() {
    resume.mutate(c.campaign_id, {
      onSuccess: () => toast("Sending again."),
      onError: (err) => toast.error(errorText(err, "Could not resume it.")),
    })
  }

  return (
    <li className="rounded-lg border border-border bg-card">
      <button type="button" onClick={onToggle} className="flex w-full flex-col gap-3 p-4 text-left sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium">{c.name}</span>
            <span className={cn("rounded-[5px] px-1.5 py-0.5 font-mono text-[10px]", look.className)}>
              {c.stalled ? "Stalled" : look.label}
            </span>
          </div>
          <p className="font-mono text-[11px] text-muted-foreground">
            {c.template_name} · {new Date(c.created_at).toLocaleString()}
          </p>
        </div>
        <div className="grid grid-cols-4 gap-4 sm:w-[360px]">
          <Stat label="Sent" value={c.counts.sent} sub={`/ ${c.counts.total}`} />
          <Stat label="Delivered" value={c.counts.delivered} sub={`${pct(c.counts.delivered, c.counts.sent)}%`} />
          <Stat label="Read" value={c.counts.read} sub={`${pct(c.counts.read, c.counts.sent)}%`} />
          <Stat label="Failed" value={c.counts.failed} />
        </div>
      </button>

      {c.status === "sending" && (
        <div className="px-4 pb-3">
          <Progress value={pct(done, c.counts.total)} />
        </div>
      )}

      {open && (
        <div className="space-y-3 border-t border-border p-4">
          {c.error && <p className="rounded-md bg-need-soft p-2 text-xs text-need">{c.error}</p>}
          {c.counts.skipped_opted_out > 0 && (
            <p className="font-mono text-[12px] text-muted-foreground">
              {c.counts.skipped_opted_out} customer{c.counts.skipped_opted_out === 1 ? "" : "s"} left out because they replied STOP.
            </p>
          )}
          {canResume && (
            <Button size="sm" onClick={doResume} disabled={resume.isPending}>
              Resume sending
            </Button>
          )}
          {detail.data && detail.data.failed.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-medium">Not delivered</p>
              <ul className="space-y-1">
                {detail.data.failed.map((f) => (
                  <li key={f.phone} className="flex flex-wrap justify-between gap-2 font-mono text-[12px]">
                    <span>{f.name || f.phone}</span>
                    <span className="text-muted-foreground">{f.error ?? "Unknown reason"}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </li>
  )
}
