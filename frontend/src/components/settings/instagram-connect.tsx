"use client"

import * as React from "react"
import { useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import API from "@/lib/axios-client"
import type { TenantSettings } from "@/services/tenant/tenant.service"

function errorText(err: unknown, fallback: string) {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback
}

/** Connects the business's Instagram professional account, so its DMs reach the agent. */
export function InstagramConnect({ tenant }: { tenant: TenantSettings }) {
  const queryClient = useQueryClient()
  const [busy, setBusy] = React.useState(false)
  const [confirm, setConfirm] = React.useState(false)
  const connected = !!tenant.instagram_connected && tenant.instagram_status !== "disconnected"

  // Instagram sends the owner back here with the result in the address.
  React.useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const ok = params.get("instagram")
    const error = params.get("instagram_error")
    if (!ok && !error) return
    if (ok === "connected") toast("Instagram connected. DMs now reach your agent.")
    if (error) toast.error(error)
    params.delete("instagram")
    params.delete("instagram_error")
    const rest = params.toString()
    window.history.replaceState(null, "", `${window.location.pathname}${rest ? `?${rest}` : ""}`)
    queryClient.invalidateQueries({ queryKey: ["tenant"] })
  }, [queryClient])

  async function connect() {
    setBusy(true)
    try {
      const res = await API.get("/instagram/connect-url")
      window.location.href = res.data.url
    } catch (err) {
      toast.error(errorText(err, "Could not start the Instagram sign-in."))
      setBusy(false)
    }
  }

  async function disconnect() {
    if (!confirm) {
      setConfirm(true)
      return
    }
    setBusy(true)
    try {
      await API.post("/instagram/disconnect")
      toast("Instagram disconnected.")
      await queryClient.invalidateQueries({ queryKey: ["tenant"] })
    } catch (err) {
      toast.error(errorText(err, "Could not disconnect Instagram."))
    } finally {
      setBusy(false)
      setConfirm(false)
    }
  }

  return (
    <section className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium">Instagram</h2>
          <p className="mt-1 font-mono text-[11px] text-muted-foreground">
            {connected
              ? `Connected${tenant.instagram_username ? ` · @${tenant.instagram_username}` : ""}. DMs reach your agent.`
              : "Not connected. Instagram DMs don't reach the agent yet."}
          </p>
        </div>
        <Badge variant={tenant.instagram_status === "error" ? "destructive" : "outline"}>
          {tenant.instagram_status === "error" ? "Needs attention" : connected ? "Live" : "Not connected"}
        </Badge>
      </div>
      {tenant.instagram_status === "error" && tenant.instagram_last_error && (
        <p className="mt-3 rounded-md bg-destructive/10 p-2 text-xs text-destructive">{tenant.instagram_last_error}</p>
      )}
      <div className="mt-3 flex gap-2">
        {(!connected || tenant.instagram_status === "error") && (
          <Button size="sm" onClick={connect} disabled={busy}>
            {busy ? "Opening Instagram..." : tenant.instagram_status === "error" ? "Reconnect" : "Connect Instagram"}
          </Button>
        )}
        {connected && (
          <Button size="sm" variant="ghost" className="text-need" onClick={disconnect} disabled={busy}>
            {confirm ? "Disconnect for good?" : "Disconnect"}
          </Button>
        )}
      </div>
      {!connected && (
        <p className="mt-2 font-mono text-[11px] text-muted-foreground">
          Needs an Instagram professional (business or creator) account.
        </p>
      )}
    </section>
  )
}
