"use client"

import { useEffect, useState } from "react"

import API from "@/lib/axios-client"

// The free backend sleeps when idle. Waking it as soon as a sign-in page opens means the
// first click doesn't wait for a cold start. The request is fire-and-forget.
export function useWakeServer() {
  useEffect(() => {
    API.get("/health/", { timeout: 90000 }).catch(() => {})
  }, [])
}

// True once a request has been running for a while, so the form can say the server is waking up.
export function useSlow(active: boolean, afterMs = 4000) {
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    if (!active) return
    const timer = setTimeout(() => setSlow(true), afterMs)
    return () => {
      clearTimeout(timer)
      setSlow(false)
    }
  }, [active, afterMs])
  return active && slow
}
