"use client"

import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useSetupReminders } from "@/hooks/setup/use-setup-reminders"

const LABELS: Record<string, { title: string; href: string; cta: string }> = {
  menu: { title: "Upload your menu", href: "/setup/menu", cta: "Upload menu" },
  whatsapp: { title: "Connect WhatsApp", href: "/setup/whatsapp", cta: "Connect" },
}

/** Shown on the dashboard home for optional setup steps the owner skipped. */
export function SetupChecklistCard() {
  const { remaining } = useSetupReminders()
  if (remaining.length === 0) return null

  return (
    <Card size="sm" className="mx-4 mt-4">
      <CardHeader>
        <CardTitle>Finish setting up</CardTitle>
        <CardDescription>
          You skipped {remaining.length === 1 ? "one step" : `${remaining.length} steps`}. Finish them whenever you&apos;re ready.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {remaining.map((step) => {
          const item = LABELS[step]
          return (
            <div key={step} className="flex items-center justify-between gap-3">
              <span className="text-sm">{item.title}</span>
              <Button size="sm" variant="outline" render={<Link href={item.href} />}>
                {item.cta}
              </Button>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}
