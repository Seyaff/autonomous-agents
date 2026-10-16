"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import {
  clearAssistantHistory,
  decideAssistantAction,
  loadAssistantHistory,
  streamAssistantTurn,
  type AssistantAction,
  type AssistantMessage,
} from "@/services/tenant/assistant.service"

export interface AgentStep {
  id: string
  name: string
  done: boolean
}

export type ChatMessage = AssistantMessage & { streaming?: boolean; steps?: AgentStep[] }

interface AssistantContextValue {
  messages: ChatMessage[]
  loading: boolean
  sending: boolean
  open: boolean
  setOpen: (open: boolean) => void
  /** Opens the panel and, with text, sends it. */
  ask: (text?: string) => void
  send: (text: string) => Promise<void>
  stop: () => void
  decide: (action: AssistantAction, confirm: boolean) => Promise<void>
  clear: () => Promise<void>
}

const AssistantContext = React.createContext<AssistantContextValue | null>(null)

export function useAssistant(): AssistantContextValue {
  const value = React.useContext(AssistantContext)
  if (!value) throw new Error("useAssistant must be used inside AssistantProvider")
  return value
}

export function AssistantProvider({ enabled, children }: { enabled: boolean; children: React.ReactNode }) {
  const router = useRouter()
  const queryClient = useQueryClient()
  const history = useQuery({ queryKey: ["assistant", "history"], queryFn: loadAssistantHistory, enabled })
  // The saved conversation is shown until the owner sends something; after that this holds the live chat.
  const [live, setLive] = React.useState<ChatMessage[] | null>(null)
  const messages = React.useMemo<ChatMessage[]>(() => live ?? history.data ?? [], [live, history.data])
  const [sending, setSending] = React.useState(false)
  const [open, setOpen] = React.useState(false)
  const abort = React.useRef<AbortController | null>(null)

  const setMessages = React.useCallback(
    (update: (prev: ChatMessage[]) => ChatMessage[]) => setLive((prev) => update(prev ?? history.data ?? [])),
    [history.data],
  )

  // Updates the reply that is being streamed, which is always the last message.
  const patchLast = React.useCallback(
    (update: (m: ChatMessage) => ChatMessage) =>
      setMessages((prev) => (prev.length ? [...prev.slice(0, -1), update(prev[prev.length - 1])] : prev)),
    [setMessages],
  )

  const send = React.useCallback(
    async (text: string) => {
      const message = text.trim()
      if (!message || sending || !enabled) return
      setSending(true)
      setMessages((prev) => [
        ...prev,
        { role: "owner", content: message },
        { role: "assistant", content: "", streaming: true, steps: [], changes: [], actions: [] },
      ])
      const controller = new AbortController()
      abort.current = controller
      let saved = 0
      try {
        await streamAssistantTurn(
          message,
          (event) => {
            switch (event.type) {
              case "token":
                patchLast((m) => ({ ...m, content: m.content + event.text }))
                break
              case "tool":
                patchLast((m) => ({ ...m, steps: [...(m.steps ?? []), { id: event.id, name: event.name, done: false }] }))
                break
              case "tool_end":
                patchLast((m) => ({
                  ...m,
                  steps: (m.steps ?? []).map((s) => (s.id === event.id ? { ...s, done: true } : s)),
                }))
                break
              case "change":
                saved += 1
                patchLast((m) => ({ ...m, changes: [...(m.changes ?? []), event.change] }))
                break
              case "confirm":
                patchLast((m) => ({ ...m, actions: [...(m.actions ?? []), event.action] }))
                break
              case "navigate":
                router.push(event.href)
                break
              case "error":
                patchLast((m) => ({ ...m, content: event.message }))
                break
              case "done":
                patchLast((m) => ({ ...m, content: m.content.trim() || event.reply }))
                break
            }
          },
          controller.signal,
        )
        if (saved) queryClient.invalidateQueries()
      } catch (err) {
        if (controller.signal.aborted) {
          patchLast((m) => ({ ...m, content: m.content || "Stopped." }))
        } else {
          const text = err instanceof Error ? err.message : "The assistant couldn't do that. Try again."
          patchLast((m) => ({ ...m, content: text }))
        }
      } finally {
        patchLast((m) => ({ ...m, streaming: false, steps: (m.steps ?? []).map((s) => ({ ...s, done: true })) }))
        abort.current = null
        setSending(false)
      }
    },
    [enabled, patchLast, queryClient, router, sending, setMessages],
  )

  const stop = React.useCallback(() => abort.current?.abort(), [])

  const ask = React.useCallback(
    (text?: string) => {
      setOpen(true)
      if (text?.trim()) void send(text)
    },
    [send],
  )

  const decide = React.useCallback(
    async (action: AssistantAction, confirm: boolean) => {
      const mark = (patch: Partial<AssistantAction>) =>
        setMessages((prev) =>
          prev.map((m) =>
            m.actions?.some((a) => a.action_id === action.action_id)
              ? { ...m, actions: m.actions.map((a) => (a.action_id === action.action_id ? { ...a, ...patch } : a)) }
              : m,
          ),
        )
      try {
        const outcome = await decideAssistantAction(action.action_id, confirm)
        mark({ status: outcome.status, result: outcome.message })
        setMessages((prev) => [...prev, { role: "assistant", content: outcome.message, changes: outcome.changes }])
        if (outcome.status === "done") {
          toast.success(outcome.message)
          queryClient.invalidateQueries()
        } else if (outcome.status === "failed") {
          toast.error(outcome.message)
        }
      } catch {
        toast.error("That didn't go through. Try again.")
      }
    },
    [queryClient, setMessages],
  )

  const clear = React.useCallback(async () => {
    if (sending) return
    await clearAssistantHistory()
    setLive([])
    queryClient.setQueryData(["assistant", "history"], [])
  }, [queryClient, sending])

  // Ctrl/⌘ + K opens the agent from anywhere in the dashboard. Escape is handled by the panel.
  React.useEffect(() => {
    if (!enabled) return
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault()
        setOpen((v) => !v)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [enabled])

  const value = React.useMemo<AssistantContextValue>(
    () => ({ messages, loading: history.isLoading, sending, open, setOpen, ask, send, stop, decide, clear }),
    [messages, history.isLoading, sending, open, ask, send, stop, decide, clear],
  )

  return <AssistantContext.Provider value={value}>{children}</AssistantContext.Provider>
}
