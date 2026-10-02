"use client"

import { useSyncExternalStore } from "react"

function subscribe(callback: () => void) {
  const id = setInterval(callback, 30_000)
  return () => clearInterval(id)
}

function getSnapshot() {
  return Date.now()
}

function getServerSnapshot() {
  return 0
}

/** Reads the clock via useSyncExternalStore — the correct way to read
 * external, non-React state like `Date.now()` (a plain call during render
 * is impure and will be flagged by the purity lint rule). Ticks every 30s. */
export function useNow() {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
}
