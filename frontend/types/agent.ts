export type AgentResponse = {
    data : string
}


export type ChatRole = "user" | "assistant"

export interface ChatMessage {
    id: string
    role: ChatRole
    content: string
}