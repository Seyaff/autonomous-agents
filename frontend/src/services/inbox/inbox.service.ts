import API from "@/lib/axios-client"
import type { MessageStatus } from "@/lib/status"

export interface MessagePreview {
  content: string
  sender: "customer" | "agent" | "human" | "system"
  timestamp: string
  type: string
}

export interface Conversation {
  conversation_id: string
  tenant_id: string
  customer_phone: string
  customer_name: string
  customer_avatar?: string | null
  status: "open" | "closed" | "archived"
  last_message: MessagePreview | null
  unread_count: number
  tags: string[]
  created_at: string
  updated_at: string
  last_activity_at: string
  // Server-computed queue group and ownership (DYNAMIC_DATA_PLAN §2).
  group?: "needs_you" | "owner_handling" | "agent_handling" | "resolved"
  handled_by?: "agent" | "owner"
  handed_over_at?: string | null
  handed_over_by_user_id?: string | null
  escalation?: {
    active: boolean
    reason: string
    summary: string
    raised_at: string
    resolved_at?: string | null
    resolved_by?: string | null
  } | null
}

export type GroupCounts = {
  needs_you: number
  owner_handling: number
  agent_handling: number
  resolved: number
}

export interface Message {
  message_id: string
  wamid?: string | null
  conversation_id: string
  tenant_id: string
  sender: "customer" | "agent" | "human" | "system"
  sender_phone?: string | null
  content: string
  type: string
  status: MessageStatus
  created_at: string
  delivered_at?: string | null
  read_at?: string | null
}

export interface ConversationListResponse {
  conversations: Conversation[]
  total: number
  page: number
  limit: number
  unread_total: number
  group_counts?: GroupCounts
}

export interface ConversationDetailResponse {
  conversation: Conversation
  messages: Message[]
  has_more: boolean
}

export interface ListConversationsParams {
  status?: string
  page?: number
  limit?: number
  search?: string
}

export const listConversations = async (
  params?: ListConversationsParams
): Promise<ConversationListResponse> => {
  const res = await API.get("/inbox/conversations", { params })
  return res.data
}

export const getConversation = async (
  conversationId: string,
  params?: { before_id?: string; limit?: number }
): Promise<ConversationDetailResponse> => {
  const res = await API.get(`/inbox/conversations/${conversationId}`, { params })
  return res.data
}

export const updateConversation = async (
  conversationId: string,
  payload: { status?: Conversation["status"]; tags?: string[] }
) => {
  const res = await API.patch(`/inbox/conversations/${conversationId}`, payload)
  return res.data
}

export const takeOverConversation = async (conversationId: string) => {
  const res = await API.post(`/inbox/conversations/${conversationId}/takeover`)
  return res.data.conversation as Conversation
}

export const handBackConversation = async (conversationId: string) => {
  const res = await API.post(`/inbox/conversations/${conversationId}/handback`)
  return res.data.conversation as Conversation
}

export const resolveEscalation = async (conversationId: string) => {
  const res = await API.post(`/inbox/conversations/${conversationId}/escalation/resolve`)
  return res.data.conversation as Conversation
}

export const markConversationRead = async (conversationId: string) => {
  const res = await API.post(`/inbox/conversations/${conversationId}/read`)
  return res.data
}

export const sendMessage = async (conversationId: string, content: string) => {
  const res = await API.post(`/inbox/conversations/${conversationId}/messages`, {
    content,
    type: "text",
  })
  return res.data
}
