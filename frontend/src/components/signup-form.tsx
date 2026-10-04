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
import { useQueryClient } from "@tanstack/react-query"
import { getUserQuery } from "@/services/auth/auth.service"
import { useGoogleLogin } from "@/hooks/auth/use-google"
import { useSlow, useWakeServer } from "@/hooks/auth/use-wake-server"
import API from "@/lib/axios-client"

export function SignupForm({
  className,
  ...props
}: React.ComponentProps<"div">) {
  const router = useRouter()
  const { mutate: loginWithGoogle, isPending: isGooglePending } = useGoogleLogin()
  const [googleOpening, setGoogleOpening] = useState(false)
  const googleBusy = isGooglePending || googleOpening
  useWakeServer()
  const startGoogle = () => {
    setGoogleOpening(true)
    setTimeout(() => setGoogleOpening(false), 15000)
    loginWithGoogle()
  }

  const [fullName, setFullName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const slow = useSlow(loading)
  const [error, setError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const handleEmailSignup = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const res = await API.post("/auth/signup", {
        full_name: fullName,
        email,
        password,
      })
      if (res.data.status === "success") {
        // Load the new session before moving on, or the gate sees the old "signed out" state.
        await queryClient.fetchQuery({ queryKey: ["me"], queryFn: getUserQuery, staleTime: 0 })
        router.push("/setup")
      }
    } catch (err: any) {
      setError(err.response ? err.response.data?.detail || "Could not complete signup. Please try again." : "The server is taking too long to respond. Wait a minute and try again. If you just signed up, your account was probably created, so log in.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={cn("flex flex-col gap-6", className)} {...props}>
      <form onSubmit={handleEmailSignup}>
        <FieldGroup>
          <div className="flex flex-col items-center gap-2 text-center">
            <div className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <GalleryVerticalEndIcon className="size-5" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight">Create an Account</h1>
            <FieldDescription>
              Already have an account? <Link href="/login" className="text-primary underline">Log in</Link>
            </FieldDescription>
          </div>

          {error && (
            <div className="rounded-md bg-destructive/15 p-3 text-sm text-destructive font-medium">
              {error}
            </div>
          )}

          <div className="flex flex-col gap-4">
            <Field>
              <FieldLabel htmlFor="fullName">Full Name / Owner Name</FieldLabel>
              <Input
                id="fullName"
                type="text"
                placeholder="Chef Gordon / Ali Khan"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
              />
            </Field>

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
                placeholder="Min. 8 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
              />
            </Field>

            <Button type="submit" disabled={loading} className="w-full">
              {loading ? "Creating Account..." : "Create Account"}
            </Button>
            {slow && (
              <p className="text-center text-sm text-muted-foreground">
                Waking up our server. After a quiet spell this can take up to a minute.
              </p>
            )}
          </div>

          <div className="relative my-2 text-center text-xs after:absolute after:inset-0 after:top-1/2 after:z-0 after:flex after:items-center after:border-t after:border-border">
            <span className="relative z-10 bg-background px-2 text-muted-foreground font-medium">
              Or sign up with
            </span>
          </div>

          <Button
            variant="outline"
            type="button"
            onClick={startGoogle}
            disabled={googleBusy || loading}
            className="w-full"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" className="w-4 h-4 mr-2">
              <path
                d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .307 5.387.307 12s5.56 12 12.173 12c3.573 0 6.267-1.173 8.373-3.36 2.16-2.16 2.84-5.213 2.84-7.667 0-.76-.053-1.467-.173-2.053H12.48z"
                fill="currentColor"
              />
            </svg>
            {googleBusy ? "Opening Google..." : "Google Account"}
          </Button>
        </FieldGroup>
      </form>
    </div>
  )
}
