"use client"

import React, { useState } from "react"
import { cn } from "cn"
import { Button } from "@/components/ui/button"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { GalleryVerticalEndIcon } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useGoogleLogin } from "@/hooks/auth/use-google"
import API from "@/lib/axios-client"

export function LoginForm({
  className,
  ...props
}: React.ComponentProps<"div">) {
  const router = useRouter()
  const { mutate: loginWithGoogle, isPending: isGooglePending } = useGoogleLogin()

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleEmailLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const res = await API.post("/auth/login", { email, password })
      if (res.data.status === "success") {
        const isOnboarded = res.data.user?.is_onboarded
        router.push(isOnboarded ? "/dashboard" : "/onboarding")
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "Invalid email or password.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={cn("flex flex-col gap-6", className)} {...props}>
      <form onSubmit={handleEmailLogin}>
        <FieldGroup>
          <div className="flex flex-col items-center gap-2 text-center">
            <div className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <GalleryVerticalEndIcon className="size-5" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight">Welcome Back</h1>
            <FieldDescription>
              Don&apos;t have an account? <Link href="/signup" className="text-primary underline">Sign up</Link>
            </FieldDescription>
          </div>

          {error && (
            <div className="rounded-md bg-destructive/15 p-3 text-sm text-destructive font-medium">
              {error}
            </div>
          )}

          <div className="flex flex-col gap-4">
            <Field>
              <FieldLabel htmlFor="email">Email</FieldLabel>
              <Input
                id="email"
                type="email"
                placeholder="owner@restaurant.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </Field>

            <Field>
              <FieldLabel htmlFor="password">Password</FieldLabel>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </Field>

            <Button type="submit" disabled={loading} className="w-full">
              {loading ? "Signing in..." : "Sign In with Email"}
            </Button>
          </div>

          <div className="relative my-2 text-center text-xs after:absolute after:inset-0 after:top-1/2 after:z-0 after:flex after:items-center after:border-t after:border-border">
            <span className="relative z-10 bg-background px-2 text-muted-foreground font-medium">
              Or continue with
            </span>
          </div>

          <Button
            variant="outline"
            type="button"
            onClick={() => loginWithGoogle()}
            disabled={isGooglePending || loading}
            className="w-full"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" className="w-4 h-4 mr-2">
              <path
                d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .307 5.387.307 12s5.56 12 12.173 12c3.573 0 6.267-1.173 8.373-3.36 2.16-2.16 2.84-5.213 2.84-7.667 0-.76-.053-1.467-.173-2.053H12.48z"
                fill="currentColor"
              />
            </svg>
            {isGooglePending ? "Connecting to Google..." : "Google Account"}
          </Button>
        </FieldGroup>
      </form>
    </div>
  )
}
