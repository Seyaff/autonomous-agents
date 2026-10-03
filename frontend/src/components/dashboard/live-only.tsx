"use client"

export function LiveOnly({ title }: { title: string }) {
  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <div className="rounded-lg border border-dashed border-border px-6 py-8 text-center">
        <p className="font-mono text-[13px] text-muted-foreground">
          {title} needs the live backend. Set NEXT_PUBLIC_USE_MOCKS=false and sign in.
        </p>
      </div>
    </div>
  )
}
