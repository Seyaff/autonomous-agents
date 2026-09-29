"use client"

import { useAuth } from "@/components/providers/auth-provider"
import { useQueryAgent } from "@/hooks/agent/query-agent-mutation"

import { useState, useRef, useEffect, FormEvent } from "react"

interface ChatMessage {
    id: string
    role: "user" | "assistant"
    content: string
}

export default function Home() {
    const [input, setInput] = useState("")
    const [messages, setMessages] = useState<ChatMessage[]>([])
    const scrollRef = useRef<HTMLDivElement>(null)

    const { user, activeTenantId } = useAuth()
    const { mutate, isPending } = useQueryAgent()

    const handleSubmit = (e: FormEvent) => {
        e.preventDefault()
        const trimmed = input.trim()
        if (!trimmed || isPending) return
        if (!user || !activeTenantId) return


        setMessages((prev) => [
            ...prev,
            { id: crypto.randomUUID(), role: "user", content: trimmed },
        ])
        setInput("")

        mutate(
            {
                query: trimmed,
                tenant_id: activeTenantId,
                tenant: {
                    tenant_id: activeTenantId,
                    user_id: user.user_id,
                    role: user.role,
                },
                customer_phone: user.email, // placeholder — no phone on User yet
                user_message: trimmed,
            },
            {
                onSuccess: (data) => {
                    setMessages((prev) => [
                        ...prev,
                        {
                            id: crypto.randomUUID(),
                            role: "assistant",
                            content: data.response,
                        },
                    ])
                },
                onError: (err: any) => {
                    setMessages((prev) => [
                        ...prev,
                        {
                            id: crypto.randomUUID(),
                            role: "assistant",
                            content: `⚠️ Error: ${err?.message ?? "Something went wrong"}`,
                        },
                    ])
                },
            }
        )
    }

    useEffect(() => {
        scrollRef.current?.scrollTo({
            top: scrollRef.current.scrollHeight,
            behavior: "smooth",
        })
    }, [messages, isPending])

    return (
        <main className="flex h-screen flex-col bg-[#f7f7f5] text-neutral-900">
            <header className="border-b border-neutral-200 bg-white/70 px-6 py-3 backdrop-blur">
                <h1 className="text-sm font-medium tracking-wide text-neutral-700">
                    Agent
                </h1>
            </header>

            <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6">
                <div className="mx-auto max-w-2xl space-y-6">
                    {messages.length === 0 && !isPending && <EmptyState />}
                    {messages.map((m) => (
                        <MessageBubble key={m.id} message={m} />
                    ))}
                    {isPending && <TypingIndicator />}
                </div>
            </div>

            <div className="border-t border-neutral-200 bg-white px-4 py-4">
                <form
                    onSubmit={handleSubmit}
                    className="mx-auto flex max-w-2xl items-end gap-2 rounded-2xl border border-neutral-300 bg-white p-2 shadow-sm focus-within:border-neutral-400"
                >
                    <textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === "Enter" && !e.shiftKey) {
                                e.preventDefault()
                                handleSubmit(e as unknown as FormEvent)
                            }
                        }}
                        rows={1}
                        placeholder="Message Agent…"
                        className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-[15px] outline-none placeholder:text-neutral-400"
                    />
                    <button
                        type="submit"
                        disabled={!input.trim() || isPending}
                        className="rounded-xl bg-neutral-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                        {isPending ? "…" : "Send"}
                    </button>
                </form>
                <p className="mx-auto mt-2 max-w-2xl text-center text-xs text-neutral-400">
                    Agent can make mistakes. Verify important info.
                </p>
            </div>
        </main>
    )
}

/* ---------- Sub-components ---------- */

function MessageBubble({ message }: { message: ChatMessage }) {
    const isUser = message.role === "user"
    return (
        <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
            <div
                className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed ${isUser
                        ? "bg-neutral-900 text-white"
                        : "bg-white text-neutral-900 shadow-sm ring-1 ring-neutral-200"
                    }`}
            >
                {message.content}
            </div>
        </div>
    )
}

function TypingIndicator() {
    return (
        <div className="flex justify-start">
            <div className="flex items-center gap-1 rounded-2xl bg-white px-4 py-3 shadow-sm ring-1 ring-neutral-200">
                <Dot delay="0ms" />
                <Dot delay="150ms" />
                <Dot delay="300ms" />
            </div>
        </div>
    )
}

function Dot({ delay }: { delay: string }) {
    return (
        <span
            className="h-1.5 w-1.5 animate-bounce rounded-full bg-neutral-400"
            style={{ animationDelay: delay }}
        />
    )
}

function EmptyState() {
    return (
        <div className="mt-24 text-center">
            <h2 className="text-2xl font-medium text-neutral-800">
                How can I help you today?
            </h2>
            <p className="mt-2 text-sm text-neutral-500">
                Ask the agent to do something, and it will get to work.
            </p>
        </div>
    )
}