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
  disableTwoFactor,
  enableTwoFactor,
  listSessions,
  startTwoFactor,
  twoFactorStatus,
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

/** Two-step sign-in: turn it on with an authenticator app, then sign in with a code. */
function TwoFactorPanel() {
  const queryClient = useQueryClient()
  const status = useQuery({ queryKey: ["account", "2fa"], queryFn: twoFactorStatus })
  const [setup, setSetup] = React.useState<{ secret: string; otpauth_uri: string } | null>(null)
  const [code, setCode] = React.useState("")
  const [recovery, setRecovery] = React.useState<string[] | null>(null)
  const [password, setPassword] = React.useState("")
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["account", "2fa"] })

  const start = useMutation({
    mutationFn: startTwoFactor,
    onSuccess: (data) => setSetup(data),
    onError: (err) => toast.error(errorText(err, "Could not start two-step sign-in.")),
  })
  const enable = useMutation({
    mutationFn: () => enableTwoFactor(code),
    onSuccess: (data) => {
      setRecovery(data.recovery_codes)
      setSetup(null)
      setCode("")
      refresh()
    },
    onError: (err) => toast.error(errorText(err, "That code isn't right.")),
  })
  const disable = useMutation({
    mutationFn: () => disableTwoFactor(password, code),
    onSuccess: () => {
      toast("Two-step sign-in is off.")
      setPassword("")
      setCode("")
      refresh()
    },
    onError: (err) => toast.error(errorText(err, "Could not turn it off.")),
  })

  if (recovery) {
    return (
      <div className="space-y-3">
        <h2 className="text-sm font-medium">Save your recovery codes</h2>
        <p className="text-xs text-muted-foreground">
          Each one works once, if you lose your phone. They won't be shown again.
        </p>
        <ul className="grid grid-cols-2 gap-2 font-mono text-sm">
          {recovery.map((c) => <li key={c}>{c}</li>)}
        </ul>
        <div className="flex justify-end">
          <Button size="sm" onClick={() => setRecovery(null)}>I've saved them</Button>
        </div>
      </div>
    )
  }

  if (!status.data) return null

  if (!status.data.enabled) {
    return (
      <div className="space-y-3">
        <div>
          <h2 className="text-sm font-medium">Two-step sign-in</h2>
          <p className="mt-1 font-mono text-[11px] text-muted-foreground">
            Adds a code from an authenticator app (Google Authenticator, Microsoft Authenticator or similar) to every sign-in.
          </p>
        </div>
        {!setup ? (
          <div className="flex justify-end">
            <Button size="sm" variant="outline" disabled={start.isPending} onClick={() => start.mutate()}>Turn on</Button>
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-sm">Add this account to your app. Enter the setup key, or open the link on your phone.</p>
            <p className="break-all rounded-md bg-muted p-2 font-mono text-xs">{setup.secret}</p>
            <a className="text-xs underline" href={setup.otpauth_uri}>Open in authenticator app</a>
            <div className="space-y-1">
              <Label htmlFor="tfa-code">6-digit code from the app</Label>
              <Input id="tfa-code" inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} />
            </div>
            <div className="flex justify-end">
              <Button size="sm" disabled={code.trim().length < 6 || enable.isPending} onClick={() => enable.mutate()}>Confirm and turn on</Button>
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div>
        <h2 className="text-sm font-medium">Two-step sign-in is on</h2>
        <p className="mt-1 font-mono text-[11px] text-muted-foreground">Recovery codes left: {status.data.recovery_codes_left}</p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="tfa-off-password">Password</Label>
        <Input id="tfa-off-password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <Label htmlFor="tfa-off-code">Code from your app</Label>
        <Input id="tfa-off-code" inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} />
      </div>
      <div className="flex justify-end">
        <Button size="sm" variant="outline" disabled={!password || code.trim().length < 6 || disable.isPending} onClick={() => disable.mutate()}>
          Turn off
        </Button>
      </div>
    </div>
  )
}

/** Signed-in devices, sign-out, password change, and two-step sign-in. */
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
      <TwoFactorPanel />

      <div className="border-t border-border pt-4">
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
