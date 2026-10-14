"use client"

import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { useCampaignActions } from "@/hooks/campaigns/use-campaigns"
import { useTemplates } from "@/hooks/templates/use-templates"
import { previewAudience, type Audience, type ParamSource } from "@/services/campaigns/campaigns.service"
import { fillTemplate } from "@/services/templates/templates.service"

const SELECT = "h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"

function errorText(err: unknown, fallback: string) {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === "string") return detail
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg).replace(/^Value error, /, "")
  return fallback
}

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = React.useState(value)
  React.useEffect(() => {
    const id = setTimeout(() => setV(value), ms)
    return () => clearTimeout(id)
  }, [value, ms])
  return v
}

function ParamField({ index, source, onChange }: { index: number; source: ParamSource; onChange: (s: ParamSource) => void }) {
  return (
    <div className="grid grid-cols-[48px_150px_1fr] items-center gap-2">
      <span className="font-mono text-[12px] text-muted-foreground">{`{{${index + 1}}}`}</span>
      <select
        aria-label={`Where value ${index + 1} comes from`}
        className={SELECT}
        value={source.kind}
        onChange={(e) => onChange({ kind: e.target.value as ParamSource["kind"], value: source.value })}
      >
        <option value="text">Fixed text</option>
        <option value="customer_name">Customer&apos;s first name</option>
      </select>
      {source.kind === "text" ? (
        <Input aria-label={`Value ${index + 1}`} value={source.value} onChange={(e) => onChange({ ...source, value: e.target.value })} />
      ) : (
        <span className="font-mono text-[11px] text-muted-foreground">&quot;there&quot; when we don&apos;t know it</span>
      )}
    </div>
  )
}

/** Sends one approved template to a group of customers. */
export function CampaignComposer({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const approved = useTemplates("APPROVED")
  const { send } = useCampaignActions()
  const [name, setName] = React.useState("")
  const [templateKey, setTemplateKey] = React.useState("")
  const [body, setBody] = React.useState<ParamSource[]>([])
  const [header, setHeader] = React.useState<ParamSource[]>([])
  const [kind, setKind] = React.useState<Audience["kind"]>("all")
  const [days, setDays] = React.useState(30)
  const [phonesText, setPhonesText] = React.useState("")

  const templates = (approved.data?.templates ?? []).filter((t) => !t.header_format || t.header_format === "TEXT")
  const template = templates.find((t) => `${t.name}:${t.language}` === templateKey) ?? null

  function pickTemplate(key: string) {
    setTemplateKey(key)
    const t = templates.find((x) => `${x.name}:${x.language}` === key)
    setBody(Array.from({ length: t?.body_variables ?? 0 }, (_, i) => ({ kind: i === 0 ? "customer_name" : "text", value: "" })))
    setHeader(Array.from({ length: t?.header_variables ?? 0 }, () => ({ kind: "text", value: "" })))
  }

  const audience: Audience = React.useMemo(
    () =>
      kind === "phones"
        ? { kind, phones: phonesText.split(/[\s,;]+/).filter(Boolean) }
        : kind === "ordered_within_days"
          ? { kind, days }
          : { kind },
    [kind, days, phonesText]
  )
  const debouncedAudience = useDebounced(audience, 400)
  const reach = useQuery({
    queryKey: ["campaigns", "audience", debouncedAudience],
    queryFn: () => previewAudience(debouncedAudience),
    enabled: open && (debouncedAudience.kind !== "phones" || (debouncedAudience.phones?.length ?? 0) > 0),
  })

  const filled = [...body, ...header].every((p) => p.kind === "customer_name" || p.value.trim())
  const canSend = name.trim() && template && filled && (reach.data?.count ?? 0) > 0

  const sample = (sources: ParamSource[]) =>
    sources.map((p) => (p.kind === "customer_name" ? (reach.data?.sample[0]?.split(" ")[0] ?? "Sana") : p.value))

  function submit() {
    if (!template) return
    send.mutate(
      {
        name: name.trim(),
        template_name: template.name,
        language: template.language,
        body_params: body,
        header_params: header,
        audience,
      },
      {
        onSuccess: (c) => {
          toast(`Sending to ${c.counts.total} customer${c.counts.total === 1 ? "" : "s"}.`)
          setName("")
          setTemplateKey("")
          setBody([])
          setHeader([])
          onOpenChange(false)
        },
        onError: (err) => toast.error(errorText(err, "Could not start the campaign.")),
      }
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-display">New campaign</DialogTitle>
          <DialogDescription>
            One approved template, sent to the customers you pick. Customers who replied STOP are left out.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="c-name">Campaign name</Label>
              <Input id="c-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Eid offer" />
            </div>
            <div className="space-y-1">
              <Label htmlFor="c-template">Template</Label>
              <select id="c-template" className={SELECT} value={templateKey} onChange={(e) => pickTemplate(e.target.value)}>
                <option value="">Pick an approved template</option>
                {templates.map((t) => (
                  <option key={`${t.name}:${t.language}`} value={`${t.name}:${t.language}`}>
                    {t.name} ({t.language})
                  </option>
                ))}
              </select>
              {!approved.isLoading && templates.length === 0 && (
                <p className="font-mono text-[11px] text-muted-foreground">No approved templates yet. Write one on the Templates page.</p>
              )}
            </div>
          </div>

          {template && (header.length > 0 || body.length > 0) && (
            <div className="space-y-2 rounded-lg border border-border p-3">
              <p className="text-xs font-medium">Values</p>
              {header.map((p, i) => (
                <ParamField key={`h${i}`} index={i} source={p} onChange={(s) => setHeader(header.map((x, j) => (j === i ? s : x)))} />
              ))}
              {body.map((p, i) => (
                <ParamField key={`b${i}`} index={i} source={p} onChange={(s) => setBody(body.map((x, j) => (j === i ? s : x)))} />
              ))}
            </div>
          )}

          <fieldset className="space-y-2">
            <legend className="mb-1 text-sm font-medium">Who gets it</legend>
            <div className="grid gap-2 sm:grid-cols-3">
              {([
                ["all", "Every customer"],
                ["ordered_within_days", "Recent customers"],
                ["phones", "A list I paste"],
              ] as const).map(([value, label]) => (
                <label
                  key={value}
                  className={`flex cursor-pointer items-center gap-2 rounded-lg border p-2.5 text-sm ${kind === value ? "border-foreground bg-muted" : "border-border"}`}
                >
                  <input type="radio" name="audience" className="sr-only" checked={kind === value} onChange={() => setKind(value)} />
                  {label}
                </label>
              ))}
            </div>
            {kind === "ordered_within_days" && (
              <div className="flex items-center gap-2 text-sm">
                Ordered in the last
                <Input aria-label="Days" type="number" min={1} max={365} className="w-20" value={days}
                  onChange={(e) => setDays(Math.max(1, Math.min(365, Number(e.target.value) || 1)))} />
                days
              </div>
            )}
            {kind === "phones" && (
              <Textarea aria-label="Phone numbers" rows={3} value={phonesText} onChange={(e) => setPhonesText(e.target.value)}
                placeholder="923001234567, +92 321 7654321 ..." />
            )}
            <p className="font-mono text-[12px] text-muted-foreground">
              {reach.isFetching
                ? "Counting..."
                : reach.data
                  ? `${reach.data.count} customer${reach.data.count === 1 ? "" : "s"}${reach.data.skipped_opted_out ? `, ${reach.data.skipped_opted_out} opted out and left out` : ""}`
                  : ""}
            </p>
          </fieldset>

          {template && (
            <div className="rounded-lg bg-muted p-3">
              <div className="space-y-1 rounded-lg bg-card p-3 text-sm shadow-sm">
                {template.header_text && <p className="font-semibold">{fillTemplate(template.header_text, sample(header))}</p>}
                <p className="whitespace-pre-wrap">{fillTemplate(template.body_text, sample(body))}</p>
                {template.footer_text && <p className="text-xs text-muted-foreground">{template.footer_text}</p>}
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button disabled={!canSend || send.isPending} onClick={submit}>
            {send.isPending ? "Starting..." : `Send to ${reach.data?.count ?? 0}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
