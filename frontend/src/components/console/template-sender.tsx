"use client"

import * as React from "react"
import Link from "next/link"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useTemplates } from "@/hooks/templates/use-templates"
import { sendTemplateMessage } from "@/services/inbox/inbox.service"
import { fillTemplate } from "@/services/templates/templates.service"

function errorText(err: unknown, fallback: string) {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback
}

/** Shown instead of the text box once 24 hours have passed since the customer wrote. */
export function TemplateSender({ conversationId }: { conversationId: string }) {
  const queryClient = useQueryClient()
  const approved = useTemplates("APPROVED")
  const [key, setKey] = React.useState("")
  const [values, setValues] = React.useState<string[]>([])
  const [headerValues, setHeaderValues] = React.useState<string[]>([])

  const templates = (approved.data?.templates ?? []).filter((t) => !t.header_format || t.header_format === "TEXT")
  const template = templates.find((t) => `${t.name}:${t.language}` === key) ?? null

  const send = useMutation({
    mutationFn: () =>
      sendTemplateMessage(conversationId, {
        name: template!.name,
        language: template!.language,
        body_params: values,
        header_params: headerValues,
      }),
    onSuccess: (res) => {
      if (res.status === "success") toast("Template sent.")
      else toast.error(res.error ?? "WhatsApp didn't accept it.")
      setKey("")
      queryClient.invalidateQueries({ queryKey: ["inbox", "conversation", conversationId] })
      queryClient.invalidateQueries({ queryKey: ["inbox", "conversations"] })
    },
    onError: (err) => toast.error(errorText(err, "Could not send the template.")),
  })

  function pick(next: string) {
    setKey(next)
    const t = templates.find((x) => `${x.name}:${x.language}` === next)
    setValues(Array.from({ length: t?.body_variables ?? 0 }, () => ""))
    setHeaderValues(Array.from({ length: t?.header_variables ?? 0 }, () => ""))
  }

  const ready = template && [...values, ...headerValues].every((v) => v.trim())

  return (
    <div className="shrink-0 space-y-2 border-t border-border bg-card p-3">
      <p className="font-mono text-[11px] text-muted-foreground">
        It&apos;s been more than 24 hours since this customer wrote. WhatsApp only allows an approved template until they reply.
      </p>
      {templates.length === 0 && !approved.isLoading ? (
        <p className="text-sm">
          No approved templates yet.{" "}
          <Link href="/dashboard/templates" className="underline underline-offset-2">Write one</Link>
        </p>
      ) : (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
          <select
            aria-label="Template"
            className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm sm:w-56"
            value={key}
            onChange={(e) => pick(e.target.value)}
          >
            <option value="">Pick a template</option>
            {templates.map((t) => (
              <option key={`${t.name}:${t.language}`} value={`${t.name}:${t.language}`}>{t.name} ({t.language})</option>
            ))}
          </select>
          {template && (
            <div className="flex flex-1 flex-col gap-2">
              {headerValues.map((v, i) => (
                <Input key={`h${i}`} aria-label="Header value" placeholder="Header value" value={v}
                  onChange={(e) => setHeaderValues(headerValues.map((x, j) => (j === i ? e.target.value : x)))} />
              ))}
              {values.map((v, i) => (
                <Input key={i} aria-label={`Value ${i + 1}`} placeholder={`{{${i + 1}}}`} value={v}
                  onChange={(e) => setValues(values.map((x, j) => (j === i ? e.target.value : x)))} />
              ))}
              <p className="whitespace-pre-wrap rounded-md bg-muted p-2 text-sm">{fillTemplate(template.body_text, values)}</p>
            </div>
          )}
          <Button size="sm" disabled={!ready || send.isPending} onClick={() => send.mutate()}>
            {send.isPending ? "Sending..." : "Send template"}
          </Button>
        </div>
      )}
    </div>
  )
}
