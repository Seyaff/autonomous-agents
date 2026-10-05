"use client"

import * as React from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { WaiterScreen } from "@/components/staff/waiter-screen"
import { LinkScreen } from "@/components/staff/link-screen"
import {
  staffMe,
  staffRoster,
  staffSignIn,
  staffSignOut,
  type RosterEntry,
  type StaffMember,
} from "@/services/staff/staff.service"

const ROLE_LABEL: Record<string, string> = { waiter: "Waiter", reception: "Reception", kitchen: "Kitchen" }

function errorText(err: unknown, fallback: string) {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback
}

/** The staff app for one restaurant: sign-in, then the waiter, kitchen or reception screen. */
export function StaffApp({ restaurant }: { restaurant: string }) {
  const queryClient = useQueryClient()
  const me = useQuery({ queryKey: ["staff", "me"], queryFn: staffMe, retry: false })
  const roster = useQuery({
    queryKey: ["staff", "roster", restaurant],
    queryFn: () => staffRoster(restaurant),
    enabled: me.isError,
  })

  // A signed-in waiter stays on the waiter screens. The browser's back button can't leave the app.
  const isWaiter = me.data?.role === "waiter"
  React.useEffect(() => {
    if (!isWaiter) return
    const stay = () => window.history.pushState(null, "", window.location.href)
    stay()
    window.addEventListener("popstate", stay)
    return () => window.removeEventListener("popstate", stay)
  }, [isWaiter])

  const notLinked = roster.isError && (roster.error as { response?: { status?: number } })?.response?.status === 403

  const [picked, setPicked] = React.useState<RosterEntry | null>(null)
  const [pin, setPin] = React.useState("")
  const [pinError, setPinError] = React.useState<string | null>(null)

  const signIn = useMutation({
    mutationFn: (args: { staff_id: string; pin: string }) => staffSignIn(restaurant, args.staff_id, args.pin),
    onSuccess: (staff: StaffMember) => {
      queryClient.setQueryData(["staff", "me"], staff)
      setPicked(null)
      setPin("")
      setPinError(null)
    },
    onError: (err) => {
      setPin("")
      setPinError(errorText(err, "Could not sign in. Try again."))
    },
  })

  const pressKey = (k: string) => {
    if (!picked || signIn.isPending) return
    if (k === "⌫") {
      setPin((p) => p.slice(0, -1))
      return
    }
    const next = (pin + k).slice(0, 4)
    setPin(next)
    setPinError(null)
    if (next.length === 4) signIn.mutate({ staff_id: picked.staff_id, pin: next })
  }

  const signOut = async () => {
    try {
      await staffSignOut()
    } finally {
      queryClient.setQueryData(["staff", "me"], null)
      queryClient.removeQueries({ queryKey: ["staff", "me"] })
      queryClient.invalidateQueries({ queryKey: ["staff", "roster", restaurant] })
    }
  }

  if (me.isPending) return <Shell title="Siyaf staff"><p className="text-sm text-muted-foreground">Loading…</p></Shell>

  if (me.data) {
    return (
      <Shell title={`${me.data.name} · ${ROLE_LABEL[me.data.role] ?? me.data.role}`} onSignOut={signOut}>
        {me.data.role === "waiter" && <WaiterScreen />}
      </Shell>
    )
  }

  if (notLinked) {
    return <LinkScreen restaurant={restaurant} kind="waiter" onLinked={() => queryClient.invalidateQueries({ queryKey: ["staff", "roster", restaurant] })} />
  }

  if (picked) {
    return (
      <Shell title="Enter your PIN" onBack={() => { setPicked(null); setPin(""); setPinError(null) }}>
        <div className="mx-auto flex max-w-xs flex-col items-center gap-4">
          <p className="text-sm text-muted-foreground">{picked.name}</p>
          <div className="font-mono text-2xl tracking-[0.4em]" aria-live="polite">{pin ? "•".repeat(pin.length) : " "}</div>
          {pinError && <p role="alert" className="text-center text-sm text-destructive">{pinError}</p>}
          <div className="grid grid-cols-3 gap-3">
            {["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "⌫"].map((k, i) => (
              <button
                key={i}
                type="button"
                disabled={!k || signIn.isPending}
                onClick={() => pressKey(k)}
                aria-label={k === "⌫" ? "Delete digit" : k || undefined}
                className="h-16 w-16 rounded-xl border border-border bg-card text-lg disabled:opacity-0"
              >
                {k}
              </button>
            ))}
          </div>
        </div>
      </Shell>
    )
  }

  return (
    <Shell title="Who is signing in?">
      {roster.isPending && <p className="text-sm text-muted-foreground">Loading names…</p>}
      {roster.isError && <p role="alert" className="text-sm text-destructive">This restaurant link doesn&apos;t work.</p>}
      {roster.data && roster.data.length === 0 && (
        <p className="text-sm text-muted-foreground">No staff yet. The owner adds people on the Staff page.</p>
      )}
      <div className="grid gap-3">
        {roster.data?.filter((r) => r.role === "waiter").map((r) => (
          <button
            key={r.staff_id}
            type="button"
            disabled={r.locked}
            onClick={() => { setPicked(r); setPin(""); setPinError(null) }}
            className="flex min-h-20 items-center justify-between rounded-2xl border-2 border-border bg-card px-5 text-left disabled:opacity-50"
          >
            <span className="text-2xl font-semibold">{r.name}</span>
            <span className="text-base text-muted-foreground">{r.locked ? "Locked. Ask the owner." : "Tap"}</span>
          </button>
        ))}
      </div>
    </Shell>
  )
}

function Shell({ title, children, onBack, onSignOut }: {
  title: string
  children: React.ReactNode
  onBack?: () => void
  onSignOut?: () => void
}) {
  return (
    <main className="mx-auto flex min-h-svh w-full max-w-xl flex-col gap-4 px-4 py-6">
      <header className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {onBack && <Button variant="ghost" onClick={onBack}>← Back</Button>}
          <h1 className="text-base font-semibold">{title}</h1>
        </div>
        {onSignOut && <Button variant="outline" onClick={onSignOut}>Sign out</Button>}
      </header>
      {children}
    </main>
  )
}
