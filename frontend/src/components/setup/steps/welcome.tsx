"use client"

import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { DialogDescription, DialogFooter, DialogTitle } from "@/components/ui/dialog"

export function WelcomeStep() {
  const router = useRouter()
  return (
    <>
      <div className="space-y-2">
        <div className="flex size-9 items-center justify-center rounded-lg bg-primary font-heading text-sm text-primary-foreground">
          S
        </div>
        <DialogTitle className="font-heading text-lg">Welcome to Siyaf</DialogTitle>
        <DialogDescription>
          Let&apos;s get your WhatsApp ordering agent ready. Six short steps, about 10 minutes. Your progress is saved after every step.
        </DialogDescription>
      </div>

      <div className="space-y-2 rounded-md border border-border p-3">
        <p className="font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground">You&apos;ll need</p>
        <ul className="list-disc space-y-1 pl-4 text-sm">
          <li>Your menu as a PDF or a photo</li>
          <li>Your opening hours and delivery areas</li>
          <li>A Facebook account and a phone number for WhatsApp</li>
        </ul>
      </div>

      <DialogFooter>
        <Button onClick={() => router.push("/setup/restaurant")}>Get started</Button>
      </DialogFooter>
    </>
  )
}
