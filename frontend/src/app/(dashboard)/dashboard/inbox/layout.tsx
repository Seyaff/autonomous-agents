import { InboxSidebar } from "@/components/inbox/inbox-sidebar"

export default function InboxLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="flex min-h-0 flex-1 overflow-hidden">
      <InboxSidebar />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        {children}
      </div>
    </div>
  )
}