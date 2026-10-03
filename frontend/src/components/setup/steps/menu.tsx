"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { useMutation } from "@tanstack/react-query"
import { AlertCircleIcon, FileTextIcon, UploadCloudIcon, WrenchIcon } from "lucide-react"
import { toast } from "sonner"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { DialogDescription, DialogFooter, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { useAuth } from "@/components/providers/auth-provider"
import { useMenuItems } from "@/hooks/setup/use-menu-items"
import { useMenuUpload, isActive } from "@/hooks/setup/use-menu-upload"
import { useSetupState } from "@/hooks/setup/use-setup-state"
import { useSetupStep } from "@/hooks/setup/use-setup-step"
import { formatMoney } from "@/lib/currency"
import { sendTestMessage, type TestChatReply } from "@/services/setup/setup.service"
import { StepError, errorDetail } from "@/components/setup/steps/common"

const MAX_BYTES = 20 * 1024 * 1024

export function MenuStep() {
  const router = useRouter()
  const { activeTenantId } = useAuth()
  const setup = useSetupState({ enabled: !!activeTenantId })
  const menu = useMenuItems(!!activeTenantId)
  const upload = useMenuUpload(!!activeTenantId)
  const { complete } = useSetupStep()
  const currency = setup.tenant?.currency ?? "USD"

  const [dragging, setDragging] = React.useState(false)
  const [replacing, setReplacing] = React.useState(false)
  const [pickError, setPickError] = React.useState<string | null>(null)
  const [question, setQuestion] = React.useState("")
  const [answer, setAnswer] = React.useState<TestChatReply | null>(null)

  const ask = useMutation({
    mutationFn: (text: string) => sendTestMessage(text),
    onSuccess: (result) => setAnswer(result),
    onError: (err) => toast.error(errorDetail(err, "Could not ask the agent.")),
  })

  function takeFile(file: File | undefined) {
    if (!file) return
    setPickError(null)
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      setPickError("Only PDF menus are supported for now.")
      return
    }
    if (file.size > MAX_BYTES) {
      setPickError("That file is over 20 MB. Try a smaller PDF.")
      return
    }
    setReplacing(false)
    upload.start.mutate(file, {
      onError: (err) => setPickError(errorDetail(err, "Could not start reading that PDF. Try again.")),
    })
  }

  const job = upload.current
  const running = job && isActive(job) ? job : null
  const failed = job && job.status === "failed" ? job : null
  const items = menu.data?.items ?? []
  const hasItems = items.length > 0
  const sourceName = menu.data?.source_filename ?? job?.filename ?? null

  function advance(action: "complete" | "skip") {
    complete.mutate({ step: "menu", action }, { onSuccess: () => router.push("/setup/hours") })
  }

  const showDropzone = !running && (replacing || (!hasItems && !failed))

  return (
    <>
      <div className="space-y-1.5">
        <DialogTitle className="font-heading text-lg">Upload your menu</DialogTitle>
        <DialogDescription>
          The agent reads your dishes and prices from this. You can change it later.
        </DialogDescription>
      </div>

      {running && (
        <div className="space-y-3 rounded-lg border border-border p-5">
          <div className="flex items-center justify-between gap-3">
            <p className="flex min-w-0 items-center gap-2 text-sm font-medium">
              <FileTextIcon className="size-4 shrink-0 text-muted-foreground" />
              <span className="truncate">{running.filename}</span>
            </p>
            <span className="font-mono text-[12px] text-muted-foreground tabular-nums">
              {running.stage === "reading" && running.chunks_total > 0
                ? `${running.chunks_done} of ${running.chunks_total} parts`
                : ""}
            </span>
          </div>
          <Progress
            value={
              running.stage === "reading" && running.chunks_total > 0
                ? Math.round((running.chunks_done / running.chunks_total) * 100)
                : null
            }
          />
          <p className="font-mono text-[12px] text-muted-foreground">{running.label}…</p>
          <p className="text-xs text-muted-foreground">
            You can leave this page. Reading keeps going, and this page picks up where it left off.
          </p>
        </div>
      )}

      {failed && !running && (
        <Alert variant="destructive">
          <AlertCircleIcon className="size-4" />
          <AlertTitle>{failed.filename} wasn&apos;t read</AlertTitle>
          <AlertDescription>
            {failed.error ?? "Something went wrong while reading the menu."}
            <div className="mt-2">
              <Button size="sm" variant="outline" onClick={() => { upload.reset(); setReplacing(true) }}>
                Upload a different PDF
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      )}

      {showDropzone && (
        <label
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            takeFile(e.dataTransfer.files?.[0])
          }}
          className={`flex cursor-pointer flex-col items-center gap-3 rounded-lg border border-dashed p-8 text-center ${
            dragging ? "border-foreground bg-muted" : "border-border"
          }`}
        >
          <UploadCloudIcon className="size-7 text-muted-foreground" />
          <span className="text-sm font-medium">Upload your menu</span>
          <span className="font-mono text-[11px] text-muted-foreground">
            PDF up to 20 MB. Photos of a printed menu aren&apos;t supported yet.
          </span>
          <span className="inline-flex h-7 items-center rounded-md border border-border px-2.5 text-sm">
            {upload.start.isPending ? "Starting..." : "Choose file"}
          </span>
          <Input
            type="file"
            accept="application/pdf,.pdf"
            className="sr-only"
            disabled={upload.start.isPending}
            onChange={(e) => takeFile(e.target.files?.[0])}
          />
        </label>
      )}

      {!running && !failed && !showDropzone && hasItems && (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <p className="flex items-center gap-2 text-sm">
              <FileTextIcon className="size-4 text-muted-foreground" />
              <span className="font-medium">{items.length} items found</span>
              {sourceName && <span className="font-mono text-[12px] text-muted-foreground">· {sourceName}</span>}
            </p>
            <Button size="sm" variant="outline" onClick={() => setReplacing(true)}>
              Replace
            </Button>
          </div>

          <div className="max-h-[200px] overflow-y-auto rounded-md border border-border">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-card text-left font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Item</th>
                  <th className="px-3 py-2 font-medium">Category</th>
                  <th className="px-3 py-2 text-right font-medium">Price</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, i) => (
                  <tr key={`${item.name}-${i}`} className="border-t border-border">
                    <td className="px-3 py-2">{item.name}</td>
                    <td className="px-3 py-2 text-muted-foreground">{item.category}</td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums">
                      {item.price == null ? "—" : formatMoney(item.price, currency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="space-y-2 border-t border-border pt-4">
            <p className="text-sm font-medium">Check what your agent knows</p>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (question.trim().length < 2 || ask.isPending) return
                ask.mutate(question.trim())
              }}
              className="flex gap-2"
            >
              <Input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask like a customer would"
                disabled={ask.isPending}
              />
              <Button type="submit" size="sm" variant="outline" disabled={ask.isPending || question.trim().length < 2}>
                {ask.isPending ? "Asking..." : "Ask"}
              </Button>
            </form>
            {answer && (
              <div className="space-y-1.5 rounded-md bg-muted p-3">
                {answer.trace[0] && (
                  <p className="flex items-center gap-1.5 font-mono text-[12px] text-ai">
                    <WrenchIcon className="size-3.5" />
                    ↳ {answer.trace[0].tool}({Object.values(answer.trace[0].args).join(", ")}) → {answer.trace[0].result_summary.slice(0, 80)}
                  </p>
                )}
                <p className="whitespace-pre-wrap text-sm">{answer.reply}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {pickError && <StepError message={pickError} />}

      {!running && !hasItems && !failed && !pickError && menu.data && (
        <p className="font-mono text-[12px] text-muted-foreground">
          Nothing read from the menu yet. Upload a PDF to continue, or skip this step for now.
        </p>
      )}

      <DialogFooter>
        <Button variant="outline" onClick={() => router.push("/setup/restaurant")} disabled={!!running}>
          Back
        </Button>
        <Button variant="ghost" onClick={() => advance("skip")} disabled={complete.isPending || !!running}>
          Skip for now
        </Button>
        <Button onClick={() => advance("complete")} disabled={!hasItems || complete.isPending || !!running}>
          Continue
        </Button>
      </DialogFooter>
    </>
  )
}
