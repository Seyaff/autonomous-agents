"use client"

import { Alert, AlertDescription } from "@/components/ui/alert"

/** The server's error text when it has one, otherwise a plain fallback. */
export function errorDetail(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === "string") return detail
  if (Array.isArray(detail) && typeof detail[0]?.msg === "string") return detail[0].msg
  return fallback
}

export function StepError({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <Alert variant="destructive">
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  )
}

/** Display-only copy of the server's country map. The server decides the real values. */
export const COUNTRY_LOCALE: Record<string, { label: string; currency: string; timezone: string }> = {
  PK: { label: "Pakistan", currency: "PKR", timezone: "Asia/Karachi" },
  AE: { label: "United Arab Emirates", currency: "AED", timezone: "Asia/Dubai" },
  SA: { label: "Saudi Arabia", currency: "SAR", timezone: "Asia/Riyadh" },
  GB: { label: "United Kingdom", currency: "GBP", timezone: "Europe/London" },
  US: { label: "United States", currency: "USD", timezone: "America/New_York" },
}
