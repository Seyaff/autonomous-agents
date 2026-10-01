"use client"

import React, { useEffect, useState } from "react"
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

export function MetaEmbeddedSignup({ onSuccess, onError, disabled = false, next = "/onboarding" }: MetaEmbeddedSignupProps) {
  const [loading, setLoading] = useState(false)
  const [sdkLoaded, setSdkLoaded] = useState(false)
  const [sdkError, setSdkError] = useState<string | null>(null)

  useEffect(() => {
    if (typeof window === "undefined") return

    if (window.FB) {
      setSdkLoaded(true)
      return
    }

    const script = document.createElement("script")
    script.src = "https://connect.facebook.net/en_US/sdk.js"
    script.async = true
    script.defer = true
    script.crossOrigin = "anonymous"
    script.onload = () => {
      window.FB.init({
        appId: process.env.NEXT_PUBLIC_META_APP_ID || "",
        version: "v19.0",
        autoLogAppEvents: true,
        xfbml: true,
      })
      setSdkLoaded(true)
    }
    script.onerror = () => {
      setSdkError("Failed to load Meta SDK")
    }
    document.body.appendChild(script)

    return () => {
      document.body.removeChild(script)
    }
  }, [])

  const handleMetaSignup = async () => {
    if (!window.FB) {
      const msg = "Meta SDK not loaded. Please refresh and try again."
      setSdkError(msg)
      toast.error(msg)
      onError?.(msg)
      return
    }

    setLoading(true)
    setSdkError(null)

    try {
      const loginResponse = await new Promise<{ authResponse?: { code: string } }>((resolve, reject) => {
        window.FB.login(
          (response: any) => {
            if (response.authResponse) {
              resolve(response)
            } else {
              reject(new Error("User cancelled or login failed"))
            }
          },
          {
            scope: "whatsapp_business_management,whatsapp_business_messaging",
            return_scopes: true,
            enable_profile_selector: true,
          }
        )
      })

      const code = loginResponse.authResponse?.code
      if (!code) {
        throw new Error("No authorization code received from Meta")
      }

      // Use the meta-embedded-signup endpoint through the proxy
      const res = await API.post("/tenant/meta-embedded-signup", {
        code,
      })

      if (res.data.status === "success") {
        toast.success("WhatsApp connected successfully!")
        onSuccess?.()
      } else {
        throw new Error(res.data.message || "Failed to connect WhatsApp")
      }
    } catch (err: any) {
      const message = err.response?.data?.detail || err.message || "Failed to connect WhatsApp"
      setSdkError(message)
      toast.error(message)
      onError?.(message)
    } finally {
      setLoading(false)
    }
  }

  if (sdkError) {
    return (
      <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive font-medium flex items-center gap-2">
        <AlertCircle className="size-5" />
        {sdkError}
      </div>
    )
  }

  return (
    <Button
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
  )
}

declare global {
  interface Window {
    FB: any
  }
}