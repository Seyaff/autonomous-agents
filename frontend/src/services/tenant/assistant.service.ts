import API from "@/lib/axios-client"

export interface AssistantChange {
  field: string
  before: unknown
  after: unknown
}

export interface AssistantMessage {
  role: "owner" | "assistant"
  content: string
  changes?: AssistantChange[]
  at?: string
}

// What the server streams back for one turn.
export type AssistantEvent =
  | { type: "token"; text: string }
  | { type: "tool"; name: string }
  | { type: "change"; change: AssistantChange }
  | { type: "error"; message: string }
  | { type: "done"; reply: string }

export const loadAssistantHistory = async (): Promise<AssistantMessage[]> => {
  const response = await API.get<{ messages: AssistantMessage[] }>("/tenant/current/assistant/history")
  return response.data.messages
}

async function postTurn(message: string): Promise<Response> {
  const init: RequestInit = {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  }
  let res = await fetch("/api/tenant/current/assistant/stream", init)
  if (res.status === 401) {
    // The access token may have just expired. Refresh the session once, then try again.
    const refreshed = await fetch("/api/auth/refresh", { method: "POST", credentials: "include" })
    if (refreshed.ok) res = await fetch("/api/tenant/current/assistant/stream", init)
  }
  return res
}

// Sends one message and calls onEvent for each piece of the reply as it arrives.
export async function streamAssistantTurn(message: string, onEvent: (event: AssistantEvent) => void): Promise<void> {
  const res = await postTurn(message)
  if (!res.ok || !res.body) throw new Error(`The assistant isn't available right now (${res.status}).`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let end = buffer.indexOf("\n\n")
    while (end !== -1) {
      const block = buffer.slice(0, end)
      buffer = buffer.slice(end + 2)
      const line = block.split("\n").find((l) => l.startsWith("data: "))
      if (line) onEvent(JSON.parse(line.slice(6)) as AssistantEvent)
      end = buffer.indexOf("\n\n")
    }
  }
}
