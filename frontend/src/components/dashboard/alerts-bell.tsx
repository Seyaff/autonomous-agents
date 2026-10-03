"use client"

import { BellIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { useAuth } from "@/components/providers/auth-provider"
import { useAlerts } from "@/hooks/alerts/use-alerts"
import { USE_MOCKS } from "@/lib/mocks"
import type { AlertSeverity } from "@/services/alerts/alerts.service"

const DOT: Record<AlertSeverity, string> = {
  critical: "bg-need",
  warning: "bg-ai",
  info: "bg-new",
}

function when(iso: string) {
  return new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })
}

/** Everything that failed or needs the owner, newest first. Stays here after a
 * reload, so an alert isn't lost just because the dashboard wasn't open. */
export function AlertsBell() {
  const { activeTenantId } = useAuth()
  const { query, readOne, readAll } = useAlerts(!!activeTenantId && !USE_MOCKS)
  const alerts = query.data?.alerts ?? []
  const unread = query.data?.unread_count ?? 0

  return (
    <Popover>
      <PopoverTrigger
        render={<Button variant="ghost" size="icon-sm" className="relative" aria-label="Alerts" />}
      >
        <BellIcon className="size-4" />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex min-w-4 items-center justify-center rounded-full bg-need px-1 font-mono text-[10px] text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <div className="flex items-center justify-between border-b border-border px-3 py-2">
          <p className="text-sm font-medium">Alerts</p>
          {unread > 0 && (
            <Button size="xs" variant="ghost" onClick={() => readAll.mutate()} disabled={readAll.isPending}>
              Mark all read
            </Button>
          )}
        </div>
        <div className="max-h-96 overflow-y-auto">
          {alerts.length === 0 ? (
            <p className="p-4 font-mono text-[12px] text-muted-foreground">
              Nothing needs you. Failures and anything that needs you will show up here.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {alerts.map((a) => (
                <li
                  key={a.id}
                  className={`flex gap-2 px-3 py-2.5 ${a.read_at ? "opacity-60" : ""}`}
                  onClick={() => {
                    if (!a.read_at) readOne.mutate(a.id)
                  }}
                >
                  <span className={`mt-1.5 size-2 shrink-0 rounded-full ${DOT[a.severity]}`} aria-hidden />
                  <div className="min-w-0 space-y-0.5">
                    <p className="text-sm font-medium">{a.title}</p>
                    {a.detail && <p className="text-xs text-muted-foreground">{a.detail}</p>}
                    <p className="font-mono text-[11px] text-muted-foreground">
                      {when(a.created_at)}
                      {a.owner_notified_whatsapp ? " · sent to your WhatsApp" : ""}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}
