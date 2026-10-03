import { Skeleton } from "@/components/ui/skeleton"

/** What the owner sees behind the setup dialog: a skeleton of the dashboard
 * home. It only uses Skeleton components and never fetches data. */
export function SetupBackdrop() {
  return (
    <div aria-hidden className="flex flex-1 flex-col gap-3 overflow-hidden p-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-16 rounded-lg" />
        ))}
      </div>
      <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[300px_1fr_400px]">
        <Skeleton className="rounded-lg" />
        <Skeleton className="rounded-lg" />
        <Skeleton className="rounded-lg" />
      </div>
    </div>
  )
}
