"use client"

import * as React from "react"

import { CounterBoard } from "@/components/staff/counter-board"

// The counter screen: /counter/<restaurant>. Linked once with the restaurant code, then it stays open.
export default function CounterPage({ params }: { params: Promise<{ restaurant: string }> }) {
  const { restaurant } = React.use(params)
  return <CounterBoard restaurant={decodeURIComponent(restaurant)} />
}
