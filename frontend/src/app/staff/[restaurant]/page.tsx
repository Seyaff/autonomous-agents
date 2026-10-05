"use client"

import * as React from "react"

import { StaffApp } from "@/components/staff/staff-app"

// The restaurant's staff link: /staff/<restaurant-slug>. Waiters, kitchen and reception sign in here with their PIN.
export default function StaffPage({ params }: { params: Promise<{ restaurant: string }> }) {
  const { restaurant } = React.use(params)
  return <StaffApp restaurant={decodeURIComponent(restaurant)} />
}
