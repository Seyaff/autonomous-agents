import API from "@/lib/axios-client"

export interface AssistantTurn {
  role: "owner" | "assistant"
  content: string
}

export interface AssistantChange {
  field: string
  before: unknown
  after: unknown
}

export interface AssistantReply {
  reply: string
  changes: AssistantChange[]
}

// Sends one message to the owner's settings assistant. The history is kept in the page, not stored on the server.
export const askSettingsAssistant = async (message: string, history: AssistantTurn[]): Promise<AssistantReply> => {
  const response = await API.post<AssistantReply>("/tenant/current/assistant", { message, history })
  return response.data
}
