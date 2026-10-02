export default function InboxEmptyState() {
  return (
    <div className="flex h-full flex-1 items-center justify-center bg-muted/30 p-6">
      <div className="rounded-lg border border-dashed border-border px-6 py-8 text-center">
        <p className="font-mono text-[13px] text-muted-foreground">
          Select a conversation from the list to see the thread.
        </p>
      </div>
    </div>
  )
}
