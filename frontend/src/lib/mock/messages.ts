import type { Message } from "@/services/inbox/inbox.service"
import { MOCK_AYESHA_ID, MOCK_HAMZA_ID, MOCK_TENANT_ID } from "@/lib/mock/conversations"

export interface AgentTraceStep {
  tool: string
  args: string
  result: string
  resultTone: "ok" | "need"
  durationS: number
}

export interface MockMessage extends Message {
  trace?: AgentTraceStep[]
}

const minutesAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString()
let seq = 0
const nextId = () => `mock_msg_${++seq}`

const BILAL_ID = `conv_${MOCK_TENANT_ID}_+923001112222`
const SANA_ID = `conv_${MOCK_TENANT_ID}_+923009998888`

export const MOCK_MESSAGES: Record<string, MockMessage[]> = {
  [BILAL_ID]: [
    {
      message_id: nextId(),
      wamid: null,
      conversation_id: BILAL_ID,
      tenant_id: MOCK_TENANT_ID,
      sender: "customer",
      sender_phone: "+92 300 1112222",
      content: "Order ORD-6A21 just arrived and the biryani is stone cold.",
      type: "text",
      status: "received",
      created_at: minutesAgo(8),
      delivered_at: null,
      read_at: null,
    },
    {
      message_id: nextId(),
      wamid: null,
      conversation_id: BILAL_ID,
      tenant_id: MOCK_TENANT_ID,
      sender: "agent",
      sender_phone: null,
      content: "I'm really sorry about that, Bilal. Let me flag this for the owner right away.",
      type: "text",
      status: "delivered",
      created_at: minutesAgo(7),
      delivered_at: minutesAgo(7),
      read_at: null,
      trace: [
        { tool: "escalate", args: "reason='cold food'", result: "flagged for owner", resultTone: "need", durationS: 0.2 },
      ],
    },
    {
      message_id: nextId(),
      wamid: null,
      conversation_id: BILAL_ID,
      tenant_id: MOCK_TENANT_ID,
      sender: "customer",
      sender_phone: "+92 300 1112222",
      content: "This is unacceptable — I want my money back, the food arrived cold.",
      type: "text",
      status: "received",
      created_at: minutesAgo(4),
      delivered_at: null,
      read_at: null,
    },
  ],
  [MOCK_AYESHA_ID]: [
    {
      message_id: nextId(),
      wamid: null,
      conversation_id: MOCK_AYESHA_ID,
      tenant_id: MOCK_TENANT_ID,
      sender: "customer",
      sender_phone: "+92 321 1234567",
      content: "Hi! Is the family deal still on today?",
      type: "text",
      status: "received",
      created_at: minutesAgo(2),
      delivered_at: null,
      read_at: null,
    },
  ],
  [MOCK_HAMZA_ID]: [
    {
      message_id: nextId(),
      wamid: null,
      conversation_id: MOCK_HAMZA_ID,
      tenant_id: MOCK_TENANT_ID,
      sender: "customer",
      sender_phone: "+92 345 1239876",
      content: "How late are you open tonight?",
      type: "text",
      status: "received",
      created_at: minutesAgo(27),
      delivered_at: null,
      read_at: null,
    },
    {
      message_id: nextId(),
      wamid: null,
      conversation_id: MOCK_HAMZA_ID,
      tenant_id: MOCK_TENANT_ID,
      sender: "agent",
      sender_phone: null,
      content: "We're open until 11pm tonight!",
      type: "text",
      status: "read",
      created_at: minutesAgo(26),
      delivered_at: minutesAgo(26),
      read_at: minutesAgo(25),
      trace: [{ tool: "search_menu", args: "query='hours'", result: "found hours", resultTone: "ok", durationS: 0.3 }],
    },
    {
      message_id: nextId(),
      wamid: null,
      conversation_id: MOCK_HAMZA_ID,
      tenant_id: MOCK_TENANT_ID,
      sender: "customer",
      sender_phone: "+92 345 1239876",
      content: "Sounds good, thanks!",
      type: "text",
      status: "received",
      created_at: minutesAgo(25),
      delivered_at: null,
      read_at: null,
    },
  ],
  [SANA_ID]: [
    {
      message_id: nextId(),
      wamid: null,
      conversation_id: SANA_ID,
      tenant_id: MOCK_TENANT_ID,
      sender: "customer",
      sender_phone: "+92 300 9998888",
      content: "Can I get 1 Chicken Karahi, pickup?",
      type: "text",
      status: "received",
      created_at: minutesAgo(100),
      delivered_at: null,
      read_at: null,
    },
    {
      message_id: nextId(),
      wamid: null,
      conversation_id: SANA_ID,
      tenant_id: MOCK_TENANT_ID,
      sender: "agent",
      sender_phone: null,
      content: "Order placed! ORD-5F12 — Rs 1,450, ready for pickup in about 20 minutes.",
      type: "text",
      status: "read",
      created_at: minutesAgo(98),
      delivered_at: minutesAgo(98),
      read_at: minutesAgo(96),
      trace: [
        { tool: "create_order", args: "items=[Chicken Karahi]", result: "ORD-5F12", resultTone: "ok", durationS: 0.5 },
      ],
    },
    {
      message_id: nextId(),
      wamid: null,
      conversation_id: SANA_ID,
      tenant_id: MOCK_TENANT_ID,
      sender: "customer",
      sender_phone: "+92 300 9998888",
      content: "Perfect, thank you so much!",
      type: "text",
      status: "received",
      created_at: minutesAgo(90),
      delivered_at: null,
      read_at: null,
    },
  ],
}
