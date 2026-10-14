"use client"

import * as React from "react"
import { RefreshCwIcon } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { LiveOnly } from "@/components/dashboard/live-only"
import { TemplateEditor } from "@/components/templates/template-editor"
import { TemplateStatusBadge } from "@/components/templates/template-status"
import { useOrderUpdates, useTemplateActions, useTemplates } from "@/hooks/templates/use-templates"
import { USE_MOCKS } from "@/lib/mocks"
import type { WaTemplate } from "@/services/templates/templates.service"

function errorText(err: unknown, fallback: string) {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback
}

export default function TemplatesPage() {
  if (USE_MOCKS) return <LiveOnly title="Templates" />
  return <Templates />
}

function Templates() {
  const list = useTemplates()
  const { sync, remove } = useTemplateActions()
  const [editorOpen, setEditorOpen] = React.useState(false)
  const [confirm, setConfirm] = React.useState<string | null>(null)

  const data = list.data
  const connected = data?.whatsapp_connected ?? true

  function runSync() {
    sync.mutate(undefined, {
      onSuccess: (res) => toast(`Synced ${res.templates.length} template${res.templates.length === 1 ? "" : "s"} from Meta.`),
      onError: (err) => toast.error(errorText(err, "Could not reach Meta. Try again.")),
    })
  }

  function del(t: WaTemplate) {
    const key = `${t.name}:${t.language}`
    if (confirm !== key) {
      setConfirm(key)
      return
    }
    remove.mutate(
      { name: t.name, language: t.language },
      {
        onSuccess: () => {
          toast(`${t.name} deleted.`)
          setConfirm(null)
        },
        onError: (err) => toast.error(errorText(err, "Could not delete it.")),
      }
    )
  }

  return (
    <div className="flex flex-1 flex-col overflow-y-auto">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border bg-card px-4 py-2">
        <div>
          <h1 className="text-sm font-medium">Templates</h1>
          <p className="font-mono text-[11px] text-muted-foreground">
            Messages Meta has approved. They reach customers after the 24-hour reply window closes.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={runSync} disabled={sync.isPending || !connected}>
            <RefreshCwIcon className={sync.isPending ? "animate-spin" : ""} /> Sync
          </Button>
          <Button size="sm" onClick={() => setEditorOpen(true)} disabled={!connected}>New template</Button>
        </div>
      </div>

      <div className="space-y-4 p-4">
        {!connected && (
          <p className="rounded-lg bg-need-soft p-3 text-sm text-need">
            Connect WhatsApp in Settings first. Templates live on your WhatsApp business account.
          </p>
        )}

        {connected && <OrderUpdatesCard />}

        <section className="rounded-lg border border-border bg-card">
          <div className="flex items-center justify-between border-b border-border px-4 py-2">
            <h2 className="text-sm font-medium">Your templates</h2>
            <span className="font-mono text-[11px] text-muted-foreground">
              {data?.synced_at ? `Synced ${new Date(data.synced_at).toLocaleString()}` : "Not synced yet"}
            </span>
          </div>
          {list.isLoading ? (
            <p className="p-4 font-mono text-[12px] text-muted-foreground">Loading...</p>
          ) : !data?.templates.length ? (
            <p className="p-4 font-mono text-[12px] text-muted-foreground">
              No templates yet. Sync to bring in the ones on your account, or write a new one.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {data.templates.map((t) => (
                <li key={`${t.name}:${t.language}`} className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-[13px] font-medium">{t.name}</span>
                      <TemplateStatusBadge status={t.status} />
                      <span className="font-mono text-[11px] text-muted-foreground">
                        {t.category.toLowerCase()} · {data.languages[t.language] ?? t.language}
                      </span>
                    </div>
                    {t.header_text && <p className="text-sm font-medium">{t.header_text}</p>}
                    <p className="whitespace-pre-wrap text-sm text-muted-foreground">{t.body_text}</p>
                    {t.rejected_reason && (
                      <p className="text-xs text-need">Meta&apos;s reason: {t.rejected_reason.replaceAll("_", " ").toLowerCase()}</p>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="shrink-0 text-need"
                    disabled={remove.isPending}
                    onClick={() => del(t)}
                  >
                    {confirm === `${t.name}:${t.language}` ? "Delete for good?" : "Delete"}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <TemplateEditor open={editorOpen} onOpenChange={setEditorOpen} languages={data?.languages ?? { en: "English" }} />
    </div>
  )
}

function OrderUpdatesCard() {
  const { state, setUp } = useOrderUpdates()
  const template = state.data?.template

  function enable() {
    setUp.mutate("en", {
      onSuccess: () => toast("Sent to Meta for review. Order updates use it once it's approved."),
      onError: (err) => toast.error(errorText(err, "Could not set it up.")),
    })
  }

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-medium">Order and booking updates after 24 hours</h2>
          {template && <TemplateStatusBadge status={template.status} />}
        </div>
        <p className="text-sm text-muted-foreground">
          {template?.status === "APPROVED"
            ? "On. When you move an order along, customers who wrote more than a day ago still get the update."
            : template
              ? "Waiting for Meta. Until it's approved, customers who wrote more than a day ago don't get updates."
              : "Off. WhatsApp blocks normal messages a day after the customer last wrote, so their updates aren't sent."}
        </p>
      </div>
      {(!template || template.status === "REJECTED" || template.status === "DISABLED") && (
        <Button size="sm" className="shrink-0" onClick={enable} disabled={setUp.isPending || state.isLoading}>
          {setUp.isPending ? "Setting up..." : template ? "Try again" : "Turn on"}
        </Button>
      )}
    </section>
  )
}
