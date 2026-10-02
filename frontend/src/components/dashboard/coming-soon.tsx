export function ComingSoon({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <div className="rounded-lg border border-dashed border-border px-6 py-8 text-center">
        <p className="font-mono text-[13px] text-muted-foreground">
          {title} isn&apos;t built yet — {detail}
        </p>
      </div>
    </div>
  )
}
