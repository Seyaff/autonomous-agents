"use client"

import React, { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Loader2, CheckCircle2, AlertCircle } from "lucide-react"
import API from "@/lib/axios-client"
import { toast } from "sonner"

interface MetaEmbeddedSignupProps {
  onSuccess?: () => void
  onError?: (error: string) => void
  disabled?: boolean
  next?: string
}

export function MetaEmbeddedSignup({
  onSuccess,
  onError,
  disabled = false,
  next = "/setup",
}: MetaEmbeddedSignupProps) {
  const [loading, setLoading] = useState(false)
  const [sdkLoaded, setSdkLoaded] = useState(false)
  const [sdkError, setSdkError] = useState<string | null>(null)

  const phoneNumberIdRef = useRef<string | null>(null)
  const wabaIdRef = useRef<string | null>(null)

  // If the SDK never arrives (blocked script, ad blocker, no network), say so
  // instead of showing "Loading Meta SDK..." forever.
  useEffect(() => {
    if (sdkLoaded || sdkError) return
    const timer = window.setTimeout(() => {
      if (!window.FB) {
        setSdkError("Meta's sign-in didn't load. Check your connection or disable any ad blocker, then reload. You can also do this later.")
      }
    }, 8000)
    return () => window.clearTimeout(timer)
  }, [sdkLoaded, sdkError])

  // Load the Meta SDK once per session
  useEffect(() => {
    if (typeof window === "undefined") return

    if (window.FB) {
      setSdkLoaded(true)
      return
    }

    const existing = document.getElementById("facebook-jssdk")
    if (existing) return

    const script = document.createElement("script")
    script.id = "facebook-jssdk"
    script.src = "https://connect.facebook.net/en_US/sdk.js"
    script.async = true
    script.defer = true
    script.crossOrigin = "anonymous"
    script.onload = () => {
      window.FB.init({
        appId: process.env.NEXT_PUBLIC_META_APP_ID || "1805909160426077",
        version: "v19.0",
        autoLogAppEvents: true,
        xfbml: true,
      })
      setSdkLoaded(true)
    }
    script.onerror = () => setSdkError("Failed to load Meta SDK")
    document.body.appendChild(script)

    // Intentionally no cleanup — Meta SDK should stay loaded for the session
  }, [])

  // Capture Embedded Signup postMessage events (phone_number_id, waba_id)
  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (!event.origin.endsWith("facebook.com")) return
      try {
        const data =
          typeof event.data === "string" ? JSON.parse(event.data) : event.data
        if (data?.type === "WA_EMBEDDED_SIGNUP") {
          console.log("EMBEDDED SIGNUP EVENT:", data)
          if (data.event === "FINISH") {
            phoneNumberIdRef.current = data.data?.phone_number_id ?? null
            wabaIdRef.current = data.data?.waba_id ?? null
          }
        }
      } catch {
        // ignore non-JSON messages
      }
    }
    window.addEventListener("message", handler)
    return () => window.removeEventListener("message", handler)
  }, [])

  const handleMetaSignup = async () => {
    if (!window.FB) {
      const msg = "Meta SDK not loaded. Please refresh and try again."
      setSdkError(msg)
      toast.error(msg)
      onError?.(msg)
      return
    }

    const configId = process.env.NEXT_PUBLIC_META_CONFIG_ID
    if (!configId) {
      const msg =
        "Meta config ID missing. Please set NEXT_PUBLIC_META_CONFIG_ID in your environment."
      setSdkError(msg)
      toast.error(msg)
      onError?.(msg)
      return
    }

    setLoading(true)
    setSdkError(null)

    try {
      const loginResponse = await new Promise<any>((resolve, reject) => {
        window.FB.login(
          (response: any) => {
            console.log("[meta-signup] FB.login response", {
              status: response?.status,
              hasAuthResponse: !!response?.authResponse,
              hasCode: !!response?.authResponse?.code,
              keys: Object.keys(response ?? {}),
            })
            if (response.authResponse) {
              resolve(response)
            } else {
              reject(new Error("User cancelled or login failed"))
            }
          },
          {
            config_id: configId || "1022729364120609",
            response_type: "code",
            override_default_response_type: true,
            extras: {
              setup: {},
              featureType: "",
              sessionInfoVersion: "3",
            },
          }
        )
      })

      const code = loginResponse.authResponse?.code
      if (!code) {
        throw new Error("No authorization code received from Meta")
      }

      console.log("[meta-signup] posting to backend", {
        phone_number_id: phoneNumberIdRef.current,
        waba_id: wabaIdRef.current,
      })
      const res = await API.post("/tenant/meta-embedded-signup", {
        code,
        phone_number_id: phoneNumberIdRef.current,
        waba_id: wabaIdRef.current,
      })
      console.log("[meta-signup] backend response", res.status, res.data)

      if (res.data?.status === "success" || res.data?.success === true) {
        toast.success("WhatsApp connected successfully!")
        onSuccess?.()
      } else {
        throw new Error(res.data?.message || "Failed to connect WhatsApp")
      }
    } catch (err: any) {
      const message =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        err.message ||
        "Failed to connect WhatsApp"
      setSdkError(message)
      toast.error(message)
      onError?.(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-3 w-full">
      {sdkError && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive font-medium flex items-center gap-2">
          <AlertCircle className="size-5 flex-shrink-0" />
          <span>{sdkError}</span>
        </div>
      )}

      <Button
        type="button"
        onClick={handleMetaSignup}
        disabled={loading || disabled || !sdkLoaded}
        className="bg-green-600 hover:bg-green-700 text-white w-full"
      >
        {loading ? (
          <>
            <Loader2 className="size-4 mr-2 animate-spin" />
            Connecting WhatsApp...
          </>
        ) : sdkLoaded ? (
          <>
            <CheckCircle2 className="size-4 mr-2" />
            Connect WhatsApp Business Account
          </>
        ) : (
          <>
            <Loader2 className="size-4 mr-2 animate-spin" />
            Loading Meta SDK...
          </>
        )}
      </Button>
    </div>
  )
}

declare global {
  interface Window {
    FB: any
  }
}