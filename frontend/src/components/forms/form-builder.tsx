"use client"

import * as React from "react"
import { ArrowDownIcon, ArrowUpIcon, PlusIcon, Trash2Icon } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { useFormActions } from "@/hooks/forms/use-forms"
import {
  FIELD_KINDS,
  FORM_CATEGORIES,
  type FieldKind,
  type FormDraftPayload,
  type FormField,
  type FormScreen,
  type WaForm,
} from "@/services/forms/forms.service"

const SELECT = "h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"
const MAX_SCREENS = 8
const MAX_FIELDS = 10

function errorText(err: unknown, fallback: string) {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === "string") return detail
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg).replace(/^Value error, /, "")
  return fallback
}

const blankField = (): FormField => ({ label: "", kind: "short_text", required: true, options: [] })
const blankScreen = (n: number): FormScreen => ({ title: n === 0 ? "Your details" : `Step ${n + 1}`, intro: "", fields: [blankField()] })

function starter(): FormDraftPayload {
  return {
    name: "",
    purpose: "",
    body: "Please fill in this short form.",
    cta: "Open form",
    submit_label: "Submit",
    category: "OTHER",
    screens: [blankScreen(0)],
  }
}

function fromForm(form: WaForm): FormDraftPayload {
  return {
    name: form.name,
    purpose: form.purpose,
    body: form.body,
    cta: form.cta,
    submit_label: form.submit_label,
    category: form.category,
    screens: form.screens.map((s) => ({ ...s, intro: s.intro ?? "", fields: s.fields.map((f) => ({ ...f, options: f.options ?? [] })) })),
  }
}

function limitFor(kind: FieldKind) {
  return FIELD_KINDS.find((k) => k.value === kind)?.limit ?? 20
}

function hasOptions(kind: FieldKind) {
  return !!FIELD_KINDS.find((k) => k.value === kind)?.options
}

/** Problems the owner can fix before saving. The server checks the same rules. */
function problemsIn(d: FormDraftPayload): string[] {
  const out: string[] = []
  if (!d.name.trim()) out.push("Give the form a name.")
  if (d.purpose.trim().length < 5) out.push("Say when the agent should send it.")
  d.screens.forEach((s, si) => {
    if (!s.title.trim()) out.push(`Screen ${si + 1} needs a title.`)
    s.fields.forEach((f, fi) => {
      const where = `Screen ${si + 1}, field ${fi + 1}`
      if (!f.label.trim()) out.push(`${where} needs a question.`)
      else if (f.label.trim().length > limitFor(f.kind)) out.push(`${where}: keep the question to ${limitFor(f.kind)} characters.`)
      if (hasOptions(f.kind) && f.options.filter((o) => o.trim()).length === 0) out.push(`${where} needs options.`)
    })
  })
  return out
}

function PhonePreview({ draft, screen }: { draft: FormDraftPayload; screen: number }) {
  const s = draft.screens[screen]
  const last = screen === draft.screens.length - 1
  return (
    <div className="rounded-[18px] border border-border bg-muted p-2">
      <div className="space-y-3 rounded-[14px] bg-card p-3 text-sm shadow-sm">
        <p className="text-center text-xs font-medium">{s?.title || "Screen title"}</p>
        {s?.intro && <p className="text-xs text-muted-foreground">{s.intro}</p>}
        {s?.fields.map((f, i) => (
          <div key={i} className="space-y-1">
            {f.kind === "opt_in" ? (
              <p className="flex items-start gap-2 text-xs"><span className="mt-0.5 size-3 shrink-0 rounded-sm border border-border" />{f.label || "Agree"}</p>
            ) : (
              <>
                <p className="text-xs text-muted-foreground">{f.label || "Question"}{!f.required && " (optional)"}</p>
                {hasOptions(f.kind) && f.kind !== "dropdown" ? (
                  <div className="space-y-1">
                    {f.options.filter((o) => o.trim()).slice(0, 4).map((o) => (
                      <p key={o} className="flex items-center gap-2 text-xs">
                        <span className={`size-3 border border-border ${f.kind === "choice" ? "rounded-full" : "rounded-sm"}`} />{o}
                      </p>
                    ))}
                  </div>
                ) : (
                  <div className={`rounded-md border border-border ${f.kind === "long_text" ? "h-10" : "h-6"}`} />
                )}
              </>
            )}
          </div>
        ))}
        <div className="rounded-full bg-ok py-1.5 text-center text-xs font-medium text-white">
          {last ? draft.submit_label || "Submit" : "Continue"}
        </div>
      </div>
    </div>
  )
}

export function FormBuilder({
  open,
  onOpenChange,
  form,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  form: WaForm | null
}) {
  const { save } = useFormActions()
  const [draft, setDraft] = React.useState<FormDraftPayload>(starter)
  const [active, setActive] = React.useState(0)

  React.useEffect(() => {
    if (!open) return
    // Opening the builder loads the form being edited, or a fresh one.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDraft(form ? fromForm(form) : starter())
    setActive(0)
  }, [open, form])

  const problems = problemsIn(draft)
  const screen = draft.screens[Math.min(active, draft.screens.length - 1)]

  function patch(p: Partial<FormDraftPayload>) {
    setDraft((d) => ({ ...d, ...p }))
  }

  function patchScreen(index: number, p: Partial<FormScreen>) {
    setDraft((d) => ({ ...d, screens: d.screens.map((s, i) => (i === index ? { ...s, ...p } : s)) }))
  }

  function patchField(fi: number, p: Partial<FormField>) {
    patchScreen(active, { fields: screen.fields.map((f, i) => (i === fi ? { ...f, ...p } : f)) })
  }

  function moveField(fi: number, by: number) {
    const fields = [...screen.fields]
    const to = fi + by
    if (to < 0 || to >= fields.length) return
    ;[fields[fi], fields[to]] = [fields[to], fields[fi]]
    patchScreen(active, { fields })
  }

  function addScreen() {
    setDraft((d) => ({ ...d, screens: [...d.screens, blankScreen(d.screens.length)] }))
    setActive(draft.screens.length)
  }

  function removeScreen(index: number) {
    setDraft((d) => ({ ...d, screens: d.screens.filter((_, i) => i !== index) }))
    setActive(Math.max(0, index - 1))
  }

  function submit() {
    const payload: FormDraftPayload = {
      ...draft,
      screens: draft.screens.map((s) => ({
        ...s,
        intro: s.intro?.trim() || null,
        fields: s.fields.map((f) => ({ ...f, label: f.label.trim(), options: hasOptions(f.kind) ? f.options.map((o) => o.trim()).filter(Boolean) : [] })),
      })),
    }
    save.mutate(
      { formId: form?.form_id, payload },
      {
        onSuccess: () => {
          toast(form?.meta_status === "PUBLISHED" ? "Saved. Publish again to send the new version." : "Saved. Publish it to let the agent use it.")
          onOpenChange(false)
        },
        onError: (err) => toast.error(errorText(err, "Could not save the form.")),
      }
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle className="font-display">{form ? "Edit form" : "New form"}</DialogTitle>
          <DialogDescription>
            Customers fill it in without leaving WhatsApp. The agent sends it when the conversation fits what you describe.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-5 md:grid-cols-[1fr_240px]">
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label htmlFor="f-name">Name</Label>
                <Input id="f-name" maxLength={60} value={draft.name} onChange={(e) => patch({ name: e.target.value })} placeholder="Booking request" />
              </div>
              <div className="space-y-1">
                <Label htmlFor="f-category">Kind</Label>
                <select id="f-category" className={SELECT} value={draft.category} onChange={(e) => patch({ category: e.target.value })}>
                  {FORM_CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
              </div>
            </div>
            <div className="space-y-1">
              <Label htmlFor="f-purpose">When should the agent send it?</Label>
              <Textarea id="f-purpose" rows={2} maxLength={300} value={draft.purpose} onChange={(e) => patch({ purpose: e.target.value })}
                placeholder="When a customer wants to book an appointment and hasn't given a date and service yet." />
            </div>
            <div className="grid gap-3 sm:grid-cols-[1fr_140px_140px]">
              <div className="space-y-1">
                <Label htmlFor="f-body">Message with the button</Label>
                <Input id="f-body" maxLength={1024} value={draft.body} onChange={(e) => patch({ body: e.target.value })} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="f-cta">Button</Label>
                <Input id="f-cta" maxLength={20} value={draft.cta} onChange={(e) => patch({ cta: e.target.value })} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="f-submit">Submit button</Label>
                <Input id="f-submit" maxLength={35} value={draft.submit_label} onChange={(e) => patch({ submit_label: e.target.value })} />
              </div>
            </div>

            <div className="space-y-3 rounded-lg border border-border p-3">
              <div className="flex flex-wrap items-center gap-1.5">
                {draft.screens.map((s, i) => (
                  <Button key={i} type="button" size="sm" variant={i === active ? "default" : "outline"} onClick={() => setActive(i)}>
                    {i + 1}. {s.title || "Screen"}
                  </Button>
                ))}
                <Button type="button" size="sm" variant="ghost" onClick={addScreen} disabled={draft.screens.length >= MAX_SCREENS}>
                  <PlusIcon /> Screen
                </Button>
              </div>

              <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
                <Input aria-label="Screen title" maxLength={30} value={screen.title} onChange={(e) => patchScreen(active, { title: e.target.value })} />
                <Button type="button" variant="ghost" size="sm" className="text-need" disabled={draft.screens.length === 1} onClick={() => removeScreen(active)}>
                  Remove screen
                </Button>
              </div>
              <Input aria-label="Text at the top (optional)" maxLength={300} value={screen.intro ?? ""} placeholder="Text at the top (optional)"
                onChange={(e) => patchScreen(active, { intro: e.target.value })} />

              <div className="space-y-2">
                {screen.fields.map((f, fi) => (
                  <div key={fi} className="space-y-2 rounded-md border border-border p-2.5">
                    <div className="grid gap-2 sm:grid-cols-[1fr_150px_auto]">
                      <Input aria-label="Question" maxLength={limitFor(f.kind)} value={f.label} placeholder="Question"
                        onChange={(e) => patchField(fi, { label: e.target.value })} />
                      <select aria-label="Answer type" className={SELECT} value={f.kind}
                        onChange={(e) => patchField(fi, { kind: e.target.value as FieldKind })}>
                        {FIELD_KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
                      </select>
                      <div className="flex items-center gap-0.5">
                        <Button type="button" variant="ghost" size="icon" aria-label="Move up" disabled={fi === 0} onClick={() => moveField(fi, -1)}><ArrowUpIcon /></Button>
                        <Button type="button" variant="ghost" size="icon" aria-label="Move down" disabled={fi === screen.fields.length - 1} onClick={() => moveField(fi, 1)}><ArrowDownIcon /></Button>
                        <Button type="button" variant="ghost" size="icon" aria-label="Remove question" disabled={screen.fields.length === 1}
                          onClick={() => patchScreen(active, { fields: screen.fields.filter((_, i) => i !== fi) })}><Trash2Icon /></Button>
                      </div>
                    </div>
                    {hasOptions(f.kind) && (
                      <Textarea aria-label="Options" rows={2} value={f.options.join("\n")} placeholder="One option per line"
                        onChange={(e) => patchField(fi, { options: e.target.value.split("\n") })} />
                    )}
                    <label className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Checkbox checked={f.required} onCheckedChange={(on: boolean) => patchField(fi, { required: on })} aria-label="Required" />
                      Required
                      <span className="ml-auto font-mono text-[11px]">{f.label.length}/{limitFor(f.kind)}</span>
                    </label>
                  </div>
                ))}
                <Button type="button" variant="outline" size="sm" disabled={screen.fields.length >= MAX_FIELDS}
                  onClick={() => patchScreen(active, { fields: [...screen.fields, blankField()] })}>
                  <PlusIcon /> Question
                </Button>
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-xs font-medium">Preview, screen {active + 1}</p>
            <PhonePreview draft={draft} screen={Math.min(active, draft.screens.length - 1)} />
            {problems.length > 0 && (
              <ul className="space-y-0.5 text-xs text-need">
                {problems.slice(0, 4).map((p) => <li key={p}>{p}</li>)}
              </ul>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button disabled={problems.length > 0 || save.isPending} onClick={submit}>
            {save.isPending ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
