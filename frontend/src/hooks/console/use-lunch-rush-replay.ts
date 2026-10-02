"use client"

import { useCallback, useRef, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { MOCK_AYESHA_ID, MOCK_HAMZA_ID, MOCK_TENANT_ID } from "@/lib/mock/conversations"
import { patchMockConversation } from "@/hooks/console/use-queue"
import { appendMockMessage } from "@/hooks/console/use-thread"
import { addMockOrder } from "@/hooks/console/use-rail"
import { incrementMockKpi } from "@/hooks/console/use-kpis"
import type { MockMessage } from "@/lib/mock/messages"
import type { MockOrder } from "@/lib/mock/orders"

function wait(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms))
}

function prefersReducedMotion() {
  if (typeof window === "undefined") return false
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches
}

let seq = 1000
function makeMessage(
  convId: string,
  partial: Pick<MockMessage, "sender" | "content"> & Partial<MockMessage>
): MockMessage {
  seq += 1
  return {
    message_id: `replay_msg_${seq}`,
    wamid: null,
    conversation_id: convId,
    tenant_id: MOCK_TENANT_ID,
    sender_phone: partial.sender === "customer" ? "unknown" : null,
    type: "text",
    status: partial.sender === "customer" ? "received" : "delivered",
    created_at: new Date().toISOString(),
    delivered_at: null,
    read_at: null,
    ...partial,
  }
}

export function useLunchRushReplay(onSelectConversation: (id: string) => void) {
  const queryClient = useQueryClient()
  const [isPlaying, setIsPlaying] = useState(false)
  const runningRef = useRef(false)

  const play = useCallback(async () => {
    if (runningRef.current) return
    runningRef.current = true
    setIsPlaying(true)

    const step = prefersReducedMotion() ? 0 : 1100

    try {
      onSelectConversation(MOCK_AYESHA_ID)

      // 1. Ayesha asks about the family deal.
      await wait(step)
      appendMockMessage(
        queryClient,
        MOCK_AYESHA_ID,
        makeMessage(MOCK_AYESHA_ID, { sender: "customer", content: "Is the family deal still available today?" })
      )
      patchMockConversation(queryClient, MOCK_AYESHA_ID, {
        last_message: {
          content: "Is the family deal still available today?",
          sender: "customer",
          timestamp: new Date().toISOString(),
          type: "text",
        },
        unread_count: 1,
        last_activity_at: new Date().toISOString(),
      })

      // 2. Agent searches the menu and replies.
      await wait(step)
      patchMockConversation(queryClient, MOCK_AYESHA_ID, { isAgentTyping: true })
      await wait(step)
      patchMockConversation(queryClient, MOCK_AYESHA_ID, { isAgentTyping: false, unread_count: 0 })
      appendMockMessage(
        queryClient,
        MOCK_AYESHA_ID,
        makeMessage(MOCK_AYESHA_ID, {
          sender: "agent",
          content:
            "Yes! The Family Deal is available until 10pm — 2 Karahi, Naan, and Drinks for Rs 1,850. Want me to place the order?",
          trace: [{ tool: "search_menu", args: "query='family deal'", result: "1 match found", resultTone: "ok", durationS: 0.4 }],
        })
      )

      // 3. Ayesha orders.
      await wait(step)
      appendMockMessage(
        queryClient,
        MOCK_AYESHA_ID,
        makeMessage(MOCK_AYESHA_ID, { sender: "customer", content: "Yes please, that sounds great!" })
      )

      // 4. Agent creates the order — it prints onto the rail, KPIs go up.
      await wait(step)
      patchMockConversation(queryClient, MOCK_AYESHA_ID, { isAgentTyping: true })
      await wait(step)
      patchMockConversation(queryClient, MOCK_AYESHA_ID, { isAgentTyping: false })
      appendMockMessage(
        queryClient,
        MOCK_AYESHA_ID,
        makeMessage(MOCK_AYESHA_ID, {
          sender: "agent",
          content: "Order placed! ORD-7F3A — Rs 1,850, arriving in about 35 minutes.",
          trace: [{ tool: "create_order", args: "items=[Family Deal]", result: "ORD-7F3A", resultTone: "ok", durationS: 0.6 }],
        })
      )

      const newOrder: MockOrder = {
        order_id: "ORD-7F3A",
        tenant_id: MOCK_TENANT_ID,
        customer_phone: "+92 321 1234567",
        customer_name: "Ayesha Raza",
        delivery_address: "Gulberg III, Block C",
        items: [{ name: "Family Deal (2 Karahi + Naan + Drinks)", quantity: 1, price: 1850 }],
        total_amount: 1850,
        payment_method: "cod",
        customer_notes: null,
        status: "pending",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        delivery_fee: 0,
        source: "ai_agent",
        eta_minutes: 35,
      }
      addMockOrder(queryClient, newOrder)
      incrementMockKpi(queryClient, "orders", 1)
      incrementMockKpi(queryClient, "revenue", 1850)
      toast("ORD-7F3A printed to the kitchen rail.")

      // 5. Hamza asks about a BOGO deal.
      await wait(step * 1.5)
      onSelectConversation(MOCK_HAMZA_ID)
      appendMockMessage(
        queryClient,
        MOCK_HAMZA_ID,
        makeMessage(MOCK_HAMZA_ID, { sender: "customer", content: "Hey, do you have any BOGO deals running this week?" })
      )
      patchMockConversation(queryClient, MOCK_HAMZA_ID, {
        last_message: {
          content: "Hey, do you have any BOGO deals running this week?",
          sender: "customer",
          timestamp: new Date().toISOString(),
          type: "text",
        },
        unread_count: 1,
        last_activity_at: new Date().toISOString(),
      })
      incrementMockKpi(queryClient, "conversations", 1)

      await wait(step)
      patchMockConversation(queryClient, MOCK_HAMZA_ID, { isAgentTyping: true })
      await wait(step)
      patchMockConversation(queryClient, MOCK_HAMZA_ID, { isAgentTyping: false, unread_count: 0 })
      appendMockMessage(
        queryClient,
        MOCK_HAMZA_ID,
        makeMessage(MOCK_HAMZA_ID, {
          sender: "agent",
          content: "Yes! Buy 1 Get 1 Free on all Pizzas, Thursdays only. Want me to add one to an order?",
          trace: [{ tool: "search_menu", args: "query='BOGO deal'", result: "1 match found", resultTone: "ok", durationS: 0.35 }],
        })
      )
    } finally {
      runningRef.current = false
      setIsPlaying(false)
    }
  }, [queryClient, onSelectConversation])

  return { play, isPlaying }
}
