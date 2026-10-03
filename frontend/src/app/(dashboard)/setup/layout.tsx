"use client"

import { usePathname } from "next/navigation"
import { SetupBackdrop } from "@/components/setup/setup-backdrop"
import { SetupDialog } from "@/components/setup/setup-dialog"
import { isSetupRoute, type SetupRoute } from "@/lib/setup"

/** Renders over the dashboard shell. The sidebar and top bar stay visible behind
 * the blurred overlay. The dialog is part of this layout, so it doesn't remount
 * when the step changes. */
export default function SetupLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const segment = pathname.split("/")[2] ?? "welcome"
  const route: SetupRoute = isSetupRoute(segment) ? segment : "welcome"

  return (
    <>
      <SetupBackdrop />
      <SetupDialog step={route}>{children}</SetupDialog>
    </>
  )
}
