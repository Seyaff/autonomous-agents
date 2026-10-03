"use client"

import { useEffect, useRef } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import API from "@/lib/axios-client"

function getWsBaseUrl(): string {
  // The websocket connects directly to the backend origin rather than
  // through Next.js's /api rewrite — rewrite-based proxying to an
  // external destination isn't reliable for a WebSocket upgrade in every
  // deployment target (e.g. Vercel -> Render).
  const httpBase =
    process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000/api/v1"
  return httpBase.replace(/^http/, "ws")
}

type WSEventType =
  | "message.new"
  | "message.status"
  | "message.read"
  | "unread.count"
  | "order.created"
  | "order.updated"
  | "order.cancelled"
  | "conversation.updated"
  | "alert.new"
  | "report.weekly_generated"

interface WSEvent {
  type: WSEventType
  payload: Record<string, unknown>
  timestamp: string
}

/**
 * Opens the owner dashboard's live websocket (/ws/inbox) and keeps the
 * relevant React Query caches fresh as events arrive — new messages,
 * delivery/read status, unread counts, and order updates. Reconnects with
 * backoff while `enabled` stays true.
 */
export function useInboxSocket(enabled: boolean) {
  const queryClient = useQueryClient()
  const retryRef = useRef(0)

  useEffect(() => {
    if (!enabled || typeof window === "undefined") return

    let socket: WebSocket | null = null
    let closedByCleanup = false
    let retryTimeout: ReturnType<typeof setTimeout> | null = null

    const scheduleRetry = () => {
      if (closedByCleanup) return
      const delay = Math.min(1000 * 2 ** retryRef.current, 15000)
      retryRef.current += 1
      retryTimeout = setTimeout(connect, delay)
    }

    const connect = async () => {
      let ticket: string
      try {
        const res = await API.post("/ws/ticket")
        ticket = res.data.ticket
      } catch {
        scheduleRetry()
        return
      }
      if (closedByCleanup) return

      socket = new WebSocket(`${getWsBaseUrl()}/ws/inbox?ticket=${encodeURIComponent(ticket)}`)

      socket.onopen = () => {
        retryRef.current = 0
      }

      socket.onmessage = (event) => {
        let parsed: WSEvent
        try {
          parsed = JSON.parse(event.data)
        } catch {
          return
        }

        switch (parsed.type) {
          case "message.new":
          case "message.status":
          case "message.read": {
            const conversationId = parsed.payload?.conversation_id as
              | string
              | undefined
            queryClient.invalidateQueries({ queryKey: ["inbox", "conversations"] })
            if (conversationId) {
              queryClient.invalidateQueries({
                queryKey: ["inbox", "conversation", conversationId],
              })
            }
            break
          }
          case "conversation.updated": {
            const updated = parsed.payload?.conversation as { conversation_id?: string } | undefined
            queryClient.invalidateQueries({ queryKey: ["inbox", "conversations"] })
            if (updated?.conversation_id) {
              queryClient.invalidateQueries({
                queryKey: ["inbox", "conversation", updated.conversation_id],
              })
            }
            break
          }
          case "alert.new": {
            const alert = parsed.payload?.alert as
              | { title?: string; detail?: string; severity?: string }
              | undefined
            queryClient.invalidateQueries({ queryKey: ["alerts"] })
            if (alert?.title) {
              const text = alert.detail ? `${alert.title}. ${alert.detail}` : alert.title
              if (alert.severity === "critical") toast.error(text)
              else toast.warning(text)
            }
            break
          }
          case "unread.count": {
            queryClient.invalidateQueries({ queryKey: ["inbox", "conversations"] })
            break
          }
          case "order.created":
          case "order.updated":
          case "order.cancelled": {
            queryClient.invalidateQueries({ queryKey: ["orders"] })
            queryClient.invalidateQueries({ queryKey: ["analytics"] })
            break
          }
          default:
            break
        }
      }

      socket.onclose = () => scheduleRetry()

      socket.onerror = () => {
        socket?.close()
      }
    }

    connect()

    return () => {
      closedByCleanup = true
      if (retryTimeout) clearTimeout(retryTimeout)
      socket?.close()
    }
  }, [enabled, queryClient])
}
