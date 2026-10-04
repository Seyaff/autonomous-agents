"use client"

import * as React from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { LiveOnly } from "@/components/dashboard/live-only"
import { SoldOutList } from "@/components/menu/sold-out-list"
import { useKnowledge } from "@/hooks/knowledge/use-knowledge"
import { USE_MOCKS } from "@/lib/mocks"
import type { KnowledgeCategory } from "@/services/knowledge/knowledge.service"

const CATEGORIES: { value: KnowledgeCategory; label: string }[] = [
  { value: "deal", label: "Deal or special" },
  { value: "policy", label: "Policy" },
  { value: "recipe", label: "Menu or recipe" },
  { value: "faq", label: "FAQ" },
]

function errorText(err: unknown, fallback: string) {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback
}

export default function MenuKnowledgePage() {
  if (USE_MOCKS) return <LiveOnly title="Menu knowledge" />
  return <MenuKnowledge />
}

function MenuKnowledge() {
  const { list, addText, uploadPdf, remove, search } = useKnowledge()
  const [title, setTitle] = React.useState("")
  const [category, setCategory] = React.useState<KnowledgeCategory>("deal")
  const [content, setContent] = React.useState("")
  const [file, setFile] = React.useState<File | null>(null)
  const [query, setQuery] = React.useState("")
  const [confirmId, setConfirmId] = React.useState<string | null>(null)

  const canSave = title.trim().length >= 2 && content.trim().length >= 5

  function saveText(e: React.FormEvent) {
    e.preventDefault()
    addText.mutate(
      { title: title.trim(), content: content.trim(), category },
      {
        onSuccess: () => {
          toast("Saved. The agent can answer from this now.")
          setTitle("")
          setContent("")
        },
        onError: (err) => toast.error(errorText(err, "Could not save that.")),
      }
    )
  }

  function uploadFile() {
    if (!file) return
    uploadPdf.mutate(file, {
      onSuccess: () => {
        toast("Menu uploaded. The agent can answer from it now.")
        setFile(null)
      },
      onError: (err) => toast.error(errorText(err, "Could not read that PDF.")),
    })
  }

  function runSearch(e: React.FormEvent) {
    e.preventDefault()
    if (query.trim().length < 2) return
    search.mutate(query.trim(), {
      onError: (err) => toast.error(errorText(err, "Search failed.")),
    })
  }

  function removeDoc(docId: string) {
    if (confirmId !== docId) {
      setConfirmId(docId)
      return
    }
    remove.mutate(docId, {
      onSuccess: () => toast("Removed. The agent no longer uses it."),
      onError: (err) => toast.error(errorText(err, "Could not remove that.")),
      onSettled: () => setConfirmId(null),
    })
  }

  const docs = list.data?.documents ?? []

  return (
    <div className="flex flex-1 flex-col overflow-y-auto">
      <div className="shrink-0 border-b border-border bg-card px-4 py-2">
        <h1 className="text-sm font-medium">Menu knowledge</h1>
        <p className="font-mono text-[11px] text-muted-foreground">
          What the agent can answer from: menus, deals, policies and FAQs
        </p>
      </div>

      <SoldOutList />

      <div className="grid gap-4 p-4 lg:grid-cols-2">
        <section className="rounded-lg border border-border bg-card p-4">
          <h2 className="text-sm font-medium">Add a menu item, deal or policy</h2>
          <form onSubmit={saveText} className="mt-3 space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="k-title">Title</Label>
              <Input id="k-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Weekend BBQ platter" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="k-category">Type</Label>
              <select
                id="k-category"
                value={category}
                onChange={(e) => setCategory(e.target.value as KnowledgeCategory)}
                className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"
              >
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="k-content">Details</Label>
              <Textarea
                id="k-content"
                rows={4}
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="Price, what is included, when it is available..."
              />
            </div>
            <Button type="submit" size="sm" disabled={!canSave || addText.isPending}>
              {addText.isPending ? "Saving..." : "Save"}
            </Button>
          </form>

          <div className="mt-6 border-t border-border pt-4">
            <h2 className="text-sm font-medium">Or upload a menu PDF</h2>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <input
                type="file"
                accept="application/pdf"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="text-sm file:mr-2 file:rounded-md file:border-0 file:bg-muted file:px-2.5 file:py-1"
              />
              <Button size="sm" variant="outline" onClick={uploadFile} disabled={!file || uploadPdf.isPending}>
                {uploadPdf.isPending ? "Uploading..." : "Upload"}
              </Button>
            </div>
          </div>
        </section>

        <section className="rounded-lg border border-border bg-card p-4">
          <h2 className="text-sm font-medium">What the agent knows ({docs.length})</h2>
          {list.isLoading ? (
            <p className="mt-3 font-mono text-[12px] text-muted-foreground">Loading...</p>
          ) : docs.length === 0 ? (
            <p className="mt-3 font-mono text-[12px] text-muted-foreground">Nothing yet. Add a menu or deal to get started.</p>
          ) : (
            <ul className="mt-3 divide-y divide-border">
              {docs.map((d) => (
                <li key={d.doc_id} className="flex items-start justify-between gap-3 py-2.5">
                  <div className="min-w-0">
                    <p className="truncate text-sm">{d.title}</p>
                    <p className="font-mono text-[11px] text-muted-foreground">
                      {d.doc_type === "pdf" ? "PDF" : d.category ?? "text"} · {d.chunks_count} parts · added{" "}
                      {new Date(d.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <Button
                    size="xs"
                    variant={confirmId === d.doc_id ? "destructive" : "ghost"}
                    onClick={() => removeDoc(d.doc_id)}
                    disabled={remove.isPending}
                  >
                    {confirmId === d.doc_id ? "Confirm remove" : "Remove"}
                  </Button>
                </li>
              ))}
            </ul>
          )}

          <div className="mt-6 border-t border-border pt-4">
            <h2 className="text-sm font-medium">Test what the agent finds</h2>
            <form onSubmit={runSearch} className="mt-3 flex gap-2">
              <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ask the way a customer would" />
              <Button type="submit" size="sm" variant="outline" disabled={search.isPending}>
                {search.isPending ? "Searching..." : "Search"}
              </Button>
            </form>
            {search.data && (
              <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-3 font-mono text-[12px]">
                {search.data.retrieved_context}
              </pre>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
