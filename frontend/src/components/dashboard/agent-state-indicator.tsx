"use client"

import { cn } from "@/lib/utils"
import { useCurrentTenant } from "@/hooks/tenant/use-current-tenant"
import { USE_MOCKS } from "@/lib/mocks"

function maskPhone(phone?: string | null) {
  if (!phone) return null
  const digits = phone.trim()
  const last4 = digits.slice(-4)
  const prefix = digits.slice(0, Math.max(digits.length - 8, 3))
  return `${prefix} •••• ${last4}`
}

export function AgentStateIndicator() {
  const { data: tenant } = useCurrentTenant()

  const connected = USE_MOCKS
    ? true
    : Boolean(tenant?.whatsapp_connected || tenant?.phone_number_id)

  const masked = USE_MOCKS ? "+92 42 •••• 1180" : maskPhone(tenant?.display_phone_number)

  // TODO(backend): there's no signal yet to distinguish "WhatsApp connection
  // failed" (--need, per DESIGN.md §4) from "never connected" — needs a
  // tenant health field. Until then this only shows on/not-connected-yet.
  return (
    <div className="flex items-center gap-2">
      <span className="relative flex size-2">
        {connected && (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ai opacity-75" />
        )}
        <span
          className={cn(
            "relative inline-flex size-2 rounded-full",
            connected ? "bg-ai" : "bg-muted-foreground"
          )}
        />
      </span>
      <span className="font-mono text-xs text-muted-foreground">
        {connected
          ? `Agent on${masked ? ` · WhatsApp ${masked}` : ""}`
          : "WhatsApp not connected yet"}
      </span>
    </div>
  )
}
