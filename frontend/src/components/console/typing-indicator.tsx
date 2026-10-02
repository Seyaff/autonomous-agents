export function TypingIndicator() {
  return (
    <div className="flex justify-end">
      <div className="flex items-center gap-1 rounded-[12px] rounded-br-[4px] bg-ai-soft px-3 py-2.5">
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="size-1.5 rounded-full bg-ai motion-safe:animate-bounce"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </div>
    </div>
  )
}
