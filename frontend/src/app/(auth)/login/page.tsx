"use client"

import { LoginForm } from "@/components/login-form"
import { useSearchParams } from "next/navigation"
import { Suspense } from "react"

function LoginPageContent() {
  const searchParams = useSearchParams()
  const next = searchParams?.get("next") || "/setup"

  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-6 bg-background p-6 md:p-10">
      <div className="w-full max-w-sm">
        <LoginForm next={next} />
      </div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="flex min-h-svh items-center justify-center">Loading...</div>}>
      <LoginPageContent />
    </Suspense>
  )
}