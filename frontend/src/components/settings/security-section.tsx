"use client"

import * as React from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  changePassword,
  listSessions,
  signOutDevice,
  signOutEverywhere,
  type DeviceSession,
} from "@/services/account/account.service"

function errorText(err: unknown, fallback: string) {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback
}

function deviceName(userAgent: string) {
  if (!userAgent) return "Unknown device"
  if (/iPhone|iPad/.test(userAgent)) return "iPhone or iPad"
  if (/Android/.test(userAgent)) return "Android phone"
  if (/Edg\//.test(userAgent)) return "Edge on computer"
  if (/Chrome\//.test(userAgent)) return "Chrome on computer"
  if (/Firefox\//.test(userAgent)) return "Firefox on computer"
  if (/Safari\//.test(userAgent)) return "Safari on computer"
  return "Browser"
}

function when(iso: string) {
  return new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })
}

/** Signed-in devices, sign-out, and password change. */
export function SecuritySection() {
  const queryClient = useQueryClient()
  const sessions = useQuery({ queryKey: ["account", "sessions"], queryFn: listSessions })
  const [current, setCurrent] = React.useState("")
  const [next, setNext] = React.useState("")
  const [confirm, setConfirm] = React.useState("")

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["account", "sessions"] })

  const signOut = useMutation({
    mutationFn: (id: string) => signOutDevice(id),
    onSuccess: () => {
      toast("That device is signed out.")
      refresh()
    },
    onError: (err) => toast.error(errorText(err, "Could not sign that device out.")),
  })

  const everywhere = useMutation({
    mutationFn: signOutEverywhere,
    onSuccess: () => {
      // This device is signed out too.
      window.location.href = "/login"
    },
    onError: (err) => toast.error(errorText(err, "Could not sign out everywhere.")),
  })

  const password = useMutation({
    mutationFn: () => changePassword(current, next),
    onSuccess: () => {
      toast("Password changed. Other devices were signed out.")
      setCurrent("")
      setNext("")
      setConfirm("")
      refresh()
    },
    onError: (err) => toast.error(errorText(err, "Could not change your password.")),
  })

  const canChange = current.length > 0 && next.length >= 8 && next === confirm

  return (
    <section className="rounded-lg border border-border bg-card p-4 space-y-5">
      <div>
        <h2 className="text-sm font-medium">Signed-in devices</h2>
        <p className="mt-1 font-mono text-[11px] text-muted-foreground">
          Each sign-in on a device is listed here. Sign out any you don't recognise.
        </p>
        <ul className="mt-3 divide-y divide-border">
          {(sessions.data ?? []).map((s: DeviceSession) => (
            <li key={s.session_id} className="flex items-center justify-between gap-3 py-2">
              <div>
                <p className="text-sm">
                  {deviceName(s.user_agent)} {s.current && <Badge variant="outline">This device</Badge>}
                </p>
                <p className="font-mono text-[11px] text-muted-foreground">Last used {when(s.last_used_at)}</p>
              </div>
              {!s.current && (
                <Button size="sm" variant="ghost" disabled={signOut.isPending} onClick={() => signOut.mutate(s.session_id)}>
                  Sign out
                </Button>
              )}
            </li>
          ))}
        </ul>
        <div className="mt-3 flex justify-end">
          <Button size="sm" variant="outline" disabled={everywhere.isPending} onClick={() => everywhere.mutate()}>
            Sign out everywhere
          </Button>
        </div>
      </div>

      <div className="space-y-3 border-t border-border pt-4">
        <h2 className="text-sm font-medium">Change password</h2>
        <div className="space-y-1">
          <Label htmlFor="pw-current">Current password</Label>
          <Input id="pw-current" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="pw-new">New password</Label>
          <Input id="pw-new" type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
          <p className="text-xs text-muted-foreground">At least 8 characters. Other devices are signed out when you save.</p>
        </div>
        <div className="space-y-1">
          <Label htmlFor="pw-confirm">Confirm new password</Label>
          <Input id="pw-confirm" type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        </div>
        <div className="flex justify-end">
          <Button size="sm" disabled={!canChange || password.isPending} onClick={() => password.mutate()}>
            {password.isPending ? "Saving…" : "Change password"}
          </Button>
        </div>
      </div>
    </section>
  )
}
