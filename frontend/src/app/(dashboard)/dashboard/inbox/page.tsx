import { MessageSquareIcon } from "lucide-react"

export default function ConversationRouter() {
  return (
    <main className="flex h-screen flex-1 items-center justify-center p-6">
      <div className="flex max-w-sm flex-col items-center gap-3 text-center">
        <div className="flex size-12 items-center justify-center rounded-full bg-muted">
          <MessageSquareIcon className="size-5 text-muted-foreground" />
        </div>
        <div className="flex flex-col gap-1">
          <h2 className="text-sm font-medium">No conversation selected</h2>
          <p className="text-xs text-muted-foreground">
            Choose a conversation from the list on the left to view its
            messages.
          </p>
        </div>
      </div>
    </main>
  )
}