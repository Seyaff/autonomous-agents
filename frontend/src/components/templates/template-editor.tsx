"use client"

import * as React from "react"
import { PlusIcon, XIcon } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { useTemplateActions } from "@/hooks/templates/use-templates"
import {
  fillTemplate,
  variablesIn,
  type TemplateButtonPayload,
  type TemplateCategory,
} from "@/services/templates/templates.service"

const SELECT = "h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"

function errorText(err: unknown, fallback: string) {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === "string") return detail
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg).replace(/^Value error, /, "")
  return fallback
}

/** Writes a template and sends it to Meta for review. */
export function TemplateEditor({
  open,
  onOpenChange,
  languages,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  languages: Record<string, string>
}) {
  const { create } = useTemplateActions()
  const [name, setName] = React.useState("")
  const [category, setCategory] = React.useState<TemplateCategory>("MARKETING")
  const [language, setLanguage] = React.useState("en")
  const [header, setHeader] = React.useState("")
  const [headerExample, setHeaderExample] = React.useState("")
  const [body, setBody] = React.useState("")
  const [examples, setExamples] = React.useState<string[]>([])
  const [footer, setFooter] = React.useState("")
  const [buttons, setButtons] = React.useState<TemplateButtonPayload[]>([])
  const bodyRef = React.useRef<HTMLTextAreaElement>(null)

  const bodyVars = variablesIn(body)
  const headerHasVar = variablesIn(header).length > 0
  const shownExamples = bodyVars.map((_, i) => examples[i] ?? "")
  const canSubmit =
    name.trim().length > 0 &&
    body.trim().length > 0 &&
    shownExamples.every((e) => e.trim()) &&
    (!headerHasVar || headerExample.trim()) &&
    buttons.every((b) => b.text.trim())

  function reset() {
    setName("")
    setCategory("MARKETING")
    setLanguage("en")
    setHeader("")
    setHeaderExample("")
    setBody("")
    setExamples([])
    setFooter("")
    setButtons([])
  }

  function insertVariable() {
    const next = (bodyVars.length ? Math.max(...bodyVars) : 0) + 1
    const el = bodyRef.current
    const token = `{{${next}}}`
    if (!el) {
      setBody(`${body}${token}`)
      return
    }
    const start = el.selectionStart ?? body.length
    const end = el.selectionEnd ?? body.length
    setBody(body.slice(0, start) + token + body.slice(end))
    requestAnimationFrame(() => {
      el.focus()
      el.setSelectionRange(start + token.length, start + token.length)
    })
  }

  function setButton(index: number, patch: Partial<TemplateButtonPayload>) {
    setButtons(buttons.map((b, i) => (i === index ? { ...b, ...patch } : b)))
  }

  function submit() {
    create.mutate(
      {
        name: name.trim(),
        category,
        language,
        header_text: header.trim() || null,
        header_example: headerHasVar ? headerExample.trim() : null,
        body: body.trim(),
        body_examples: shownExamples.map((e) => e.trim()),
        footer: footer.trim() || null,
        buttons: buttons.map((b) => ({ ...b, text: b.text.trim() })),
      },
      {
        onSuccess: () => {
          toast("Sent to Meta for review. It can be used once it's approved.")
          reset()
          onOpenChange(false)
        },
        onError: (err) => toast.error(errorText(err, "Meta didn't accept the template.")),
      }
    )
  }

  const preview = fillTemplate(body, shownExamples)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="font-display">New template</DialogTitle>
          <DialogDescription>
            Meta reviews every template before it can be sent. Review usually takes minutes, sometimes up to a day.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-5 md:grid-cols-[1fr_260px]">
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="space-y-1 sm:col-span-3">
                <Label htmlFor="t-name">Name</Label>
                <Input id="t-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="eid_offer" />
                <p className="font-mono text-[11px] text-muted-foreground">Lowercase letters, numbers and underscores. Customers don&apos;t see it.</p>
              </div>
              <div className="space-y-1">
                <Label htmlFor="t-category">Type</Label>
                <select id="t-category" className={SELECT} value={category} onChange={(e) => setCategory(e.target.value as TemplateCategory)}>
                  <option value="MARKETING">Marketing (offers, news)</option>
                  <option value="UTILITY">Utility (orders, bookings)</option>
                </select>
              </div>
              <div className="space-y-1">
                <Label htmlFor="t-language">Language</Label>
                <select id="t-language" className={SELECT} value={language} onChange={(e) => setLanguage(e.target.value)}>
                  {Object.entries(languages).map(([code, label]) => (
                    <option key={code} value={code}>{label}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="space-y-1">
              <Label htmlFor="t-header">Header (optional)</Label>
              <Input id="t-header" maxLength={60} value={header} onChange={(e) => setHeader(e.target.value)} placeholder="Eid sale" />
              {headerHasVar && (
                <Input
                  aria-label="Header example"
                  value={headerExample}
                  onChange={(e) => setHeaderExample(e.target.value)}
                  placeholder="Example for the header variable"
                />
              )}
            </div>

            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <Label htmlFor="t-body">Message</Label>
                <Button type="button" variant="ghost" size="sm" onClick={insertVariable}>
                  <PlusIcon /> Variable
                </Button>
              </div>
              <Textarea
                id="t-body"
                ref={bodyRef}
                rows={5}
                maxLength={1024}
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="Hi {{1}}, Eid Mubarak! Get {{2}} off everything this week."
              />
              <p className="font-mono text-[11px] text-muted-foreground">
                Variables like {"{{1}}"} are filled in when you send. A variable can&apos;t be the first or last thing in the message.
              </p>
            </div>

            {bodyVars.length > 0 && (
              <div className="space-y-2 rounded-lg border border-border p-3">
                <p className="text-xs font-medium">Examples for Meta&apos;s review</p>
                {bodyVars.map((n, i) => (
                  <div key={n} className="flex items-center gap-2">
                    <span className="w-10 shrink-0 font-mono text-[12px] text-muted-foreground">{`{{${n}}}`}</span>
                    <Input
                      aria-label={`Example for variable ${n}`}
                      value={shownExamples[i]}
                      onChange={(e) => {
                        const next = [...shownExamples]
                        next[i] = e.target.value
                        setExamples(next)
                      }}
                      placeholder={i === 0 ? "Sana" : "20%"}
                    />
                  </div>
                ))}
              </div>
            )}

            <div className="space-y-1">
              <Label htmlFor="t-footer">Footer (optional)</Label>
              <Input id="t-footer" maxLength={60} value={footer} onChange={(e) => setFooter(e.target.value)} placeholder="Reply STOP to stop offers" />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Buttons (optional)</Label>
                <div className="flex gap-1">
                  <Button type="button" variant="outline" size="sm" disabled={buttons.length >= 10}
                    onClick={() => setButtons([...buttons, { type: "QUICK_REPLY", text: "" }])}>
                    Reply
                  </Button>
                  <Button type="button" variant="outline" size="sm"
                    disabled={buttons.filter((b) => b.type === "URL").length >= 2}
                    onClick={() => setButtons([...buttons, { type: "URL", text: "", url: "https://" }])}>
                    Link
                  </Button>
                  <Button type="button" variant="outline" size="sm"
                    disabled={buttons.some((b) => b.type === "PHONE_NUMBER")}
                    onClick={() => setButtons([...buttons, { type: "PHONE_NUMBER", text: "", phone_number: "+92" }])}>
                    Call
                  </Button>
                </div>
              </div>
              {buttons.map((b, i) => (
                <div key={i} className="grid grid-cols-[1fr_1fr_auto] items-center gap-2">
                  <Input aria-label="Button text" maxLength={25} value={b.text} placeholder="Button text"
                    onChange={(e) => setButton(i, { text: e.target.value })} />
                  {b.type === "QUICK_REPLY" ? (
                    <span className="font-mono text-[11px] text-muted-foreground">Customer taps to reply</span>
                  ) : b.type === "URL" ? (
                    <Input aria-label="Link" value={b.url ?? ""} onChange={(e) => setButton(i, { url: e.target.value })} />
                  ) : (
                    <Input aria-label="Phone number" value={b.phone_number ?? ""} onChange={(e) => setButton(i, { phone_number: e.target.value })} />
                  )}
                  <Button type="button" variant="ghost" size="icon" aria-label="Remove button"
                    onClick={() => setButtons(buttons.filter((_, j) => j !== i))}>
                    <XIcon />
                  </Button>
                </div>
              ))}
              {category === "MARKETING" && !buttons.some((b) => b.type === "QUICK_REPLY" && /stop/i.test(b.text)) && (
                <p className="font-mono text-[11px] text-muted-foreground">
                  Tip: a &quot;Stop promotions&quot; reply button lets customers opt out in one tap.
                </p>
              )}
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-xs font-medium">Preview</p>
            <div className="rounded-lg bg-muted p-3">
              <div className="space-y-1.5 rounded-lg bg-card p-3 text-sm shadow-sm">
                {header && <p className="font-semibold">{fillTemplate(header, [headerExample])}</p>}
                <p className="whitespace-pre-wrap">{preview || <span className="text-muted-foreground">Your message</span>}</p>
                {footer && <p className="text-xs text-muted-foreground">{footer}</p>}
              </div>
              {buttons.length > 0 && (
                <div className="mt-1 space-y-1">
                  {buttons.map((b, i) => (
                    <div key={i} className="rounded-lg bg-card py-1.5 text-center text-sm text-ai shadow-sm">
                      {b.text || "Button"}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button disabled={!canSubmit || create.isPending} onClick={submit}>
            {create.isPending ? "Sending..." : "Send for review"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
