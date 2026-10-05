"use client"

import * as React from "react"
import { useMutation } from "@tanstack/react-query"
import { toast } from "sonner"

import { linkIpad, type DeviceKind } from "@/services/staff/staff.service"

const TITLE: Record<DeviceKind, string> = {
  waiter: "Link this waiter iPad",
  kitchen: "Link the kitchen screen",
  counter: "Link the counter screen",
}

function errorText(err: unknown, fallback: string) {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback
}

/** First use of a screen: type the restaurant code the owner shows. After that the screen stays linked. */
export function LinkScreen({ restaurant, kind, onLinked }: { restaurant: string; kind: DeviceKind; onLinked: () => void }) {
  const [code, setCode] = React.useState("")
  const link = useMutation({
    mutationFn: () => linkIpad(restaurant, code, kind),
    onSuccess: () => { toast.success("Linked."); onLinked() },
    onError: (err) => toast.error(errorText(err, "That code isn't right.")),
  })
  return (
    <main className="mx-auto flex min-h-svh w-full max-w-md flex-col justify-center gap-5 px-5 py-8">
      <h1 className="text-2xl font-semibold">{TITLE[kind]}</h1>
      <p className="text-base text-muted-foreground">
        Ask the owner for the restaurant code. You only type it once on this screen.
      </p>
      <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); if (code.length === 6) link.mutate() }}>
        <input
          inputMode="numeric"
          maxLength={6}
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
          placeholder="6-digit code"
          aria-label="Restaurant code"
          className="h-16 rounded-2xl border-2 border-border bg-card px-4 text-center font-mono text-3xl tracking-[0.3em]"
        />
        <button
          type="submit"
          disabled={code.length !== 6 || link.isPending}
          className="min-h-16 rounded-2xl bg-foreground text-lg font-semibold text-background disabled:opacity-50"
        >
          {link.isPending ? "Linking…" : "Link this screen"}
        </button>
      </form>
    </main>
  )
}
