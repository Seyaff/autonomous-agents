"use client"

import * as React from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { LiveOnly } from "@/components/dashboard/live-only"
import { FormBuilder } from "@/components/forms/form-builder"
import { useFormActions, useFormResponses, useForms } from "@/hooks/forms/use-forms"
import { USE_MOCKS } from "@/lib/mocks"
import { cn } from "@/lib/utils"
import { getFormPreview, type WaForm } from "@/services/forms/forms.service"

function errorText(err: unknown, fallback: string) {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback
}

function statusOf(f: WaForm): { label: string; className: string } {
  if (f.meta_status === "PUBLISHED" && f.has_unpublished_changes) return { label: "Changes not published", className: "bg-ai-soft text-ai" }
  if (f.meta_status === "PUBLISHED") return { label: "Live", className: "bg-ok-soft text-ok" }
  if (f.status === "error") return { label: "Needs fixing", className: "bg-need-soft text-need" }
  return { label: "Draft", className: "bg-muted text-muted-foreground" }
}

export default function FormsPage() {
  if (USE_MOCKS) return <LiveOnly title="Forms" />
  return <Forms />
}

function Forms() {
  const list = useForms()
  const [editing, setEditing] = React.useState<WaForm | null>(null)
  const [builderOpen, setBuilderOpen] = React.useState(false)
  const [openId, setOpenId] = React.useState<string | null>(null)
  const forms = list.data?.forms ?? []
  const connected = list.data?.whatsapp_connected ?? true

  function edit(form: WaForm | null) {
    setEditing(form)
    setBuilderOpen(true)
  }

  return (
    <div className="flex flex-1 flex-col overflow-y-auto">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border bg-card px-4 py-2">
        <div>
          <h1 className="text-sm font-medium">Forms</h1>
          <p className="font-mono text-[11px] text-muted-foreground">In-chat forms the agent sends on WhatsApp</p>
        </div>
        <Button size="sm" onClick={() => edit(null)}>New form</Button>
      </div>

      <div className="space-y-2 p-4">
        {!connected && (
          <p className="rounded-lg bg-need-soft p-3 text-sm text-need">
            Connect WhatsApp in Settings to publish forms. You can build them now.
          </p>
        )}
        {list.isLoading ? (
          <p className="font-mono text-[12px] text-muted-foreground">Loading...</p>
        ) : forms.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-6 text-center">
            <p className="text-sm">No forms yet.</p>
            <p className="mt-1 font-mono text-[12px] text-muted-foreground">
              A booking request, an enquiry, a feedback survey: build it once and the agent sends it when it fits.
            </p>
          </div>
        ) : (
          <ul className="space-y-2">
            {forms.map((f) => (
              <FormRow key={f.form_id} form={f} connected={connected} open={openId === f.form_id}
                onToggle={() => setOpenId(openId === f.form_id ? null : f.form_id)} onEdit={() => edit(f)} />
            ))}
          </ul>
        )}
      </div>

      <FormBuilder open={builderOpen} onOpenChange={setBuilderOpen} form={editing} />
    </div>
  )
}

function FormRow({ form: f, connected, open, onToggle, onEdit }: {
  form: WaForm
  connected: boolean
  open: boolean
  onToggle: () => void
  onEdit: () => void
}) {
  const { publish, remove } = useFormActions()
  const responses = useFormResponses(open ? f.form_id : null)
  const [confirmDelete, setConfirmDelete] = React.useState(false)
  const [previewing, setPreviewing] = React.useState(false)
  const look = statusOf(f)
  const canPublish = connected && (f.meta_status !== "PUBLISHED" || f.has_unpublished_changes)
  const questions = f.screens.reduce((n, s) => n + s.fields.length, 0)

  function doPublish() {
    publish.mutate(f.form_id, {
      onSuccess: () => toast(`${f.name} is live. The agent can send it now.`),
      onError: (err) => toast.error(errorText(err, "WhatsApp didn't accept the form.")),
    })
  }

  async function openPreview() {
    setPreviewing(true)
    try {
      const { preview_url } = await getFormPreview(f.form_id)
      if (preview_url) window.open(preview_url, "_blank", "noopener")
      else toast("Publish the form first to see Meta's preview.")
    } catch {
      toast.error("Could not get the preview.")
    } finally {
      setPreviewing(false)
    }
  }

  function doDelete() {
    if (!confirmDelete) {
      setConfirmDelete(true)
      return
    }
    remove.mutate(f.form_id, {
      onSuccess: () => toast(`${f.name} deleted.`),
      onError: (err) => toast.error(errorText(err, "Could not delete it.")),
    })
  }

  return (
    <li className="rounded-lg border border-border bg-card">
      <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-start sm:justify-between">
        <button type="button" onClick={onToggle} className="min-w-0 flex-1 space-y-1 text-left">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium">{f.name}</span>
            <span className={cn("rounded-[5px] px-1.5 py-0.5 font-mono text-[10px]", look.className)}>{look.label}</span>
          </div>
          <p className="text-sm text-muted-foreground">{f.purpose}</p>
          <p className="font-mono text-[11px] text-muted-foreground">
            {f.screens.length} screen{f.screens.length === 1 ? "" : "s"} · {questions} question{questions === 1 ? "" : "s"} · {f.responses} response{f.responses === 1 ? "" : "s"}
          </p>
        </button>
        <div className="flex shrink-0 flex-wrap gap-1.5">
          <Button size="sm" variant="outline" onClick={onEdit}>Edit</Button>
          {f.meta_flow_id && (
            <Button size="sm" variant="outline" onClick={openPreview} disabled={previewing}>Preview</Button>
          )}
          {canPublish && (
            <Button size="sm" onClick={doPublish} disabled={publish.isPending}>
              {publish.isPending ? "Publishing..." : f.meta_status === "PUBLISHED" ? "Publish changes" : "Publish"}
            </Button>
          )}
          <Button size="sm" variant="ghost" className="text-need" onClick={doDelete} disabled={remove.isPending}>
            {confirmDelete ? "Delete for good?" : "Delete"}
          </Button>
        </div>
      </div>

      {f.validation_errors.length > 0 && (
        <ul className="mx-4 mb-3 space-y-0.5 rounded-md bg-need-soft p-2 text-xs text-need">
          {f.validation_errors.map((e) => <li key={e}>{e}</li>)}
        </ul>
      )}

      {open && (
        <div className="border-t border-border p-4">
          <p className="mb-2 text-xs font-medium">Responses</p>
          {responses.isLoading ? (
            <p className="font-mono text-[12px] text-muted-foreground">Loading...</p>
          ) : !responses.data?.responses.length ? (
            <p className="font-mono text-[12px] text-muted-foreground">No responses yet.</p>
          ) : (
            <ul className="space-y-2">
              {responses.data.responses.map((r) => (
                <li key={r.response_id} className="rounded-md border border-border p-2.5">
                  <p className="font-mono text-[11px] text-muted-foreground">
                    {r.customer_phone} · {new Date(r.received_at).toLocaleString()}
                  </p>
                  <dl className="mt-1 grid gap-x-4 gap-y-0.5 text-sm sm:grid-cols-[auto_1fr]">
                    {r.answers.map((a, i) => (
                      <React.Fragment key={i}>
                        <dt className="text-muted-foreground">{a.label}</dt>
                        <dd>{a.value}</dd>
                      </React.Fragment>
                    ))}
                  </dl>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </li>
  )
}
