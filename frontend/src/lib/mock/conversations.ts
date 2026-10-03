import type { Conversation } from "@/services/inbox/inbox.service"

export type QueueGroup = "needs_you" | "owner_handling" | "agent_handling" | "resolved"

export interface MockConversation extends Conversation {
  group: QueueGroup
  escalated: boolean
  escalationReason?: string
  takeoverByOwner: boolean
  isAgentTyping: boolean
}

export const MOCK_TENANT_ID = "daal-dough-gulberg"

const minutesAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString()

export const MOCK_AYESHA_ID = `conv_${MOCK_TENANT_ID}_+923211234567`
export const MOCK_HAMZA_ID = `conv_${MOCK_TENANT_ID}_+923451239876`

export const MOCK_CONVERSATIONS: MockConversation[] = [
  {
    conversation_id: `conv_${MOCK_TENANT_ID}_+923001112222`,
    tenant_id: MOCK_TENANT_ID,
    customer_phone: "+92 300 1112222",
    customer_name: "Bilal Ahmed",
    customer_avatar: null,
    status: "open",
    last_message: {
      content: "This is unacceptable — I want my money back, the food arrived cold.",
      sender: "customer",
      timestamp: minutesAgo(4),
      type: "text",
    },
    unread_count: 1,
    tags: [],
    created_at: minutesAgo(40),
    updated_at: minutesAgo(4),
    last_activity_at: minutesAgo(4),
    group: "needs_you",
    escalated: true,
    escalationReason: "Refund request — food arrived cold",
    takeoverByOwner: false,
    isAgentTyping: false,
  },
  {
    conversation_id: MOCK_AYESHA_ID,
    tenant_id: MOCK_TENANT_ID,
    customer_phone: "+92 321 1234567",
    customer_name: "Ayesha Raza",
    customer_avatar: null,
    status: "open",
    last_message: {
      content: "Hi! Is the family deal still on today?",
      sender: "customer",
      timestamp: minutesAgo(2),
      type: "text",
    },
    unread_count: 1,
    tags: [],
    created_at: minutesAgo(10),
    updated_at: minutesAgo(2),
    last_activity_at: minutesAgo(2),
    group: "agent_handling",
    escalated: false,
    takeoverByOwner: false,
    isAgentTyping: false,
  },
  {
    conversation_id: MOCK_HAMZA_ID,
    tenant_id: MOCK_TENANT_ID,
    customer_phone: "+92 345 1239876",
    customer_name: "Hamza Siddiqui",
    customer_avatar: null,
    status: "open",
    last_message: {
      content: "Sounds good, thanks!",
      sender: "agent",
      timestamp: minutesAgo(25),
      type: "text",
    },
    unread_count: 0,
    tags: [],
    created_at: minutesAgo(60),
    updated_at: minutesAgo(25),
    last_activity_at: minutesAgo(25),
    group: "agent_handling",
    escalated: false,
    takeoverByOwner: false,
    isAgentTyping: false,
  },
  {
    conversation_id: `conv_${MOCK_TENANT_ID}_+923009998888`,
    tenant_id: MOCK_TENANT_ID,
    customer_phone: "+92 300 9998888",
    customer_name: "Sana Malik",
    customer_avatar: null,
    status: "closed",
    last_message: {
      content: "Perfect, thank you so much!",
      sender: "customer",
      timestamp: minutesAgo(90),
      type: "text",
    },
    unread_count: 0,
    tags: [],
    created_at: minutesAgo(120),
    updated_at: minutesAgo(90),
    last_activity_at: minutesAgo(90),
    group: "resolved",
    escalated: false,
    takeoverByOwner: false,
    isAgentTyping: false,
  },
]
