"use client"

import * as React from "react"

import { KitchenBoard } from "@/components/staff/kitchen-board"

// The kitchen screen: /kitchen/<restaurant>. Linked once with the restaurant code, then it stays open.
export default function KitchenPage({ params }: { params: Promise<{ restaurant: string }> }) {
  const { restaurant } = React.use(params)
  return <KitchenBoard restaurant={decodeURIComponent(restaurant)} />
}
