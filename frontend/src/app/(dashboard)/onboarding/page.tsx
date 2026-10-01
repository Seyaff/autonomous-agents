"use client"

import React, { useState, useCallback } from "react"
import { useRouter } from "next/navigation"
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  Button,
} from "@/components/ui/button"
import {
  Input,
} from "@/components/ui/input"
import {
  Label,
} from "@/components/ui/label"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Separator,
} from "@/components/ui/separator"
import {
  CheckCircle2,
  ChevronRight,
  ChevronLeft,
  Store,
  Truck,
  FileUp,
  MessageSquareShare,
  Loader2,
  AlertCircle,
  X,
} from "lucide-react"
import API from "@/lib/axios-client"
import { MetaEmbeddedSignup } from "@/components/MetaEmbeddedSignup"
import { toast } from "sonner"
import { useAuth } from "@/components/providers/auth-provider"

const STEPS = [
  { id: 1, label: "Profile", icon: Store, href: "#profile" },
  { id: 2, label: "Delivery", icon: Truck, href: "#delivery" },
  { id: 3, label: "Menu", icon: FileUp, href: "#menu" },
  { id: 4, label: "WhatsApp", icon: MessageSquareShare, href: "#whatsapp" },
] as const

type StepId = 1 | 2 | 3 | 4

interface OnboardingData {
  // Step 1
  businessName: string
  businessPhone: string
  address: string
  currency: string
  // Step 2
  flatDeliveryFee: string
  prepTime: string
  // Step 3
  pdfFile: File | null
  // Step 4
  whatsAppConnected: boolean
}

const INITIAL_DATA: OnboardingData = {
  businessName: "",
  businessPhone: "",
  address: "",
  currency: "USD",
  flatDeliveryFee: "2.50",
  prepTime: "30",
  pdfFile: null,
  whatsAppConnected: false,
}

export default function OnboardingPage() {
  const router = useRouter()
  const { completeOnboarding } = useAuth()
  const [step, setStep] = useState<StepId>(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tenantId, setTenantId] = useState<string | null>(null)
  const [data, setData] = useState<OnboardingData>(INITIAL_DATA)

  const updateData = useCallback((field: keyof OnboardingData, value: any) => {
    setData(prev => ({ ...prev, [field]: value }))
  }, [])

  const goToStep = (newStep: StepId) => {
    setError(null)
    setStep(newStep)
  }

  const nextStep = () => {
    if (step < 4) goToStep((step + 1) as StepId)
  }

  const prevStep = () => {
    if (step > 1) goToStep((step - 1) as StepId)
  }

  const handleCreateRestaurant = async () => {
    if (!data.businessName.trim()) return
    setError(null)
    setLoading(true)
    try {
      const res = await API.post("/tenant/create", {
        business_name: data.businessName,
        business_phone: data.businessPhone,
        address: data.address,
        currency: data.currency,
        timezone: "UTC",
        operating_hours: [
          { day: "Monday", open_time: "09:00", close_time: "22:00", is_closed: false },
          { day: "Tuesday", open_time: "09:00", close_time: "22:00", is_closed: false },
          { day: "Wednesday", open_time: "09:00", close_time: "22:00", is_closed: false },
          { day: "Thursday", open_time: "09:00", close_time: "22:00", is_closed: false },
          { day: "Friday", open_time: "09:00", close_time: "23:00", is_closed: false },
          { day: "Saturday", open_time: "09:00", close_time: "23:00", is_closed: false },
          { day: "Sunday", open_time: "10:00", close_time: "22:00", is_closed: false },
        ]
      })

      if (res.data.status === "success") {
        setTenantId(res.data.tenant_id)
        nextStep()
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "Could not save restaurant profile.")
    } finally {
      setLoading(false)
    }
  }

  const handleSaveDeliverySettings = async () => {
    setError(null)
    setLoading(true)
    try {
      await API.patch("/tenant/current", {
        flat_delivery_fee: parseFloat(data.flatDeliveryFee) || 0.0,
        avg_prep_time_minutes: parseInt(data.prepTime) || 30
      })
      nextStep()
    } catch (err: any) {
      setError("Could not save delivery settings.")
    } finally {
      setLoading(false)
    }
  }

  const handleUploadMenuPdf = async () => {
    if (!data.pdfFile) {
      nextStep()
      return
    }

    setLoading(true)
    setError(null)
    try {
      const formData = new FormData()
      formData.append("file", data.pdfFile)

      // Don't set Content-Type header - let browser set it with boundary
      const res = await API.post("/tenant/upload-menu-pdf", formData)

      // Backend returns result directly: { status, chunks_indexed, ... }
      if (res.data.status === "success") {
        nextStep()
      } else {
        setError(res.data.message || "Failed to index the menu PDF.")
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to upload menu PDF. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  const handleWhatsAppSuccess = async () => {
    if (!tenantId) return
    try {
      await completeOnboarding(tenantId)
      toast.success("WhatsApp connected! Welcome to your dashboard.")
      router.push("/dashboard")
    } catch {
      toast.error("Failed to complete onboarding")
    }
  }

  const handleWhatsAppError = (error: string) => {
    setError(error)
  }

  const renderStepIndicator = () => (
    <div className="flex items-center justify-between mb-8 border-b pb-4">
      {STEPS.map((s) => (
        <div
          key={s.id}
          className={`flex flex-col items-center gap-2 ${
            step === s.id ? "text-primary font-semibold" :
            step > s.id ? "text-green-600 font-medium" : "text-muted-foreground"
          }`}
        >
          <div className={`size-10 rounded-full flex items-center justify-center text-sm font-medium transition-all ${
            step === s.id ? "bg-primary text-primary-foreground shadow-lg" :
            step > s.id ? "bg-green-500 text-white" : "bg-muted"
          }`}>
            {step > s.id ? <CheckCircle2 className="size-5" /> : s.id}
          </div>
          <span className="text-xs font-medium">{s.label}</span>
        </div>
      ))}
    </div>
  )

  const renderStepContent = () => {
    switch (step) {
      case 1:
        return (
          <div className="space-y-6">
            <div className="text-center mb-4">
              <div className="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary mx-auto mb-4">
                <Store className="size-6" />
              </div>
              <h3 className="text-xl font-bold">Restaurant Profile</h3>
              <p className="text-sm text-muted-foreground">Your AI agent will use these details to introduce your restaurant</p>
            </div>

            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="bname" className="text-sm font-medium">Restaurant / Brand Name <span className="text-destructive">*</span></Label>
                <Input
                  id="bname"
                  placeholder="e.g. Spice Symphony, Lahore Bistro"
                  value={data.businessName}
                  onChange={(e) => updateData("businessName", e.target.value)}
                  required
                  autoFocus
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="bphone" className="text-sm font-medium">Public Contact Phone</Label>
                <Input
                  id="bphone"
                  placeholder="+1 555-0199 / +92 300 1234567"
                  value={data.businessPhone}
                  onChange={(e) => updateData("businessPhone", e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="baddr" className="text-sm font-medium">Restaurant Physical Address</Label>
                <Input
                  id="baddr"
                  placeholder="123 Food Street, Downtown"
                  value={data.address}
                  onChange={(e) => updateData("address", e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="currency" className="text-sm font-medium">Currency Code</Label>
                <Input
                  id="currency"
                  placeholder="USD, PKR, EUR, GBP"
                  value={data.currency}
                  onChange={(e) => updateData("currency", e.target.value.toUpperCase())}
                  maxLength={3}
                />
              </div>
            </div>
          </div>
        )

      case 2:
        return (
          <div className="space-y-6">
            <div className="text-center mb-4">
              <div className="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary mx-auto mb-4">
                <Truck className="size-6" />
              </div>
              <h3 className="text-xl font-bold">Delivery & Kitchen Settings</h3>
              <p className="text-sm text-muted-foreground">Configure charges and prep times for automatic order calculations</p>
            </div>

            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="fee" className="text-sm font-medium">Flat Delivery Fee ({data.currency})</Label>
                <Input
                  id="fee"
                  type="number"
                  step="0.5"
                  min="0"
                  value={data.flatDeliveryFee}
                  onChange={(e) => updateData("flatDeliveryFee", e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="prep" className="text-sm font-medium">Average Prep & Delivery Time (minutes)</Label>
                <Input
                  id="prep"
                  type="number"
                  min="5"
                  max="120"
                  value={data.prepTime}
                  onChange={(e) => updateData("prepTime", e.target.value)}
                />
              </div>
            </div>
          </div>
        )

      case 3:
        return (
          <div className="space-y-6">
            <div className="text-center mb-4">
              <div className="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary mx-auto mb-4">
                <FileUp className="size-6" />
              </div>
              <h3 className="text-xl font-bold">Upload Menu & Pricing PDF</h3>
              <p className="text-sm text-muted-foreground">Our vector RAG engine indexes dish names, ingredients, and prices so the AI never hallucinates</p>
            </div>

            <div className="border-2 border-dashed rounded-xl p-8 text-center space-y-4">
              <FileUp className="size-12 mx-auto text-muted-foreground/50" />
              <div>
                <Label htmlFor="pdf" className="cursor-pointer text-primary font-semibold hover:underline inline-flex items-center gap-2">
                  <span>Choose PDF file</span>
                  <ChevronRight className="size-4" />
                </Label>
                <input
                  id="pdf"
                  type="file"
                  accept=".pdf,application/pdf"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (file) {
                      if (file.size > 5 * 1024 * 1024) {
                        toast.error("File size must be less than 5MB")
                        return
                      }
                      updateData("pdfFile", file)
                    }
                  }}
                />
              </div>
              {data.pdfFile ? (
                <div className="flex items-center justify-center gap-3 px-4 py-3 bg-green-50 rounded-lg border border-green-200">
                  <FileUp className="size-5 text-green-600" />
                  <div className="text-left">
                    <p className="text-sm font-medium text-green-800">{data.pdfFile.name}</p>
                    <p className="text-xs text-green-600">{(data.pdfFile.size / 1024).toFixed(1)} KB</p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => updateData("pdfFile", null)}
                    className="text-green-600 hover:text-green-700"
                  >
                    <X className="size-4" />
                  </Button>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">PDF menus, price sheets, or store policies (max 5MB)</p>
              )}
            </div>
          </div>
        )

      case 4:
        return (
          <div className="space-y-6">
            <div className="text-center mb-4">
              <div className="flex size-12 items-center justify-center rounded-xl bg-green-100 text-green-600 mx-auto mb-4">
                <MessageSquareShare className="size-6" />
              </div>
              <h3 className="text-xl font-bold">Connect WhatsApp Business</h3>
              <p className="text-sm text-muted-foreground">Authenticate with Meta to connect your official WhatsApp Business number</p>
            </div>

            <Card className="border-green-200 bg-green-50/50">
              <CardContent className="pt-6">
                <div className="rounded-lg border p-4 space-y-3 bg-white">
                  <div className="flex items-center gap-3">
                    <div className="size-10 rounded-lg bg-green-100 flex items-center justify-center">
                      <MessageSquareShare className="size-5 text-green-600" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-sm">Meta Embedded Signup</h4>
                      <p className="text-xs text-muted-foreground">
                        Click below to authenticate with Meta and grant WhatsApp Cloud API permissions.
                      </p>
                    </div>
                  </div>
                </div>

                <MetaEmbeddedSignup
                  onSuccess={handleWhatsAppSuccess}
                  onError={handleWhatsAppError}
                  disabled={data.whatsAppConnected}
                />

                {data.whatsAppConnected && (
                  <div className="rounded-md bg-green-100 text-green-800 p-3 text-sm font-medium flex items-center gap-2">
                    <CheckCircle2 className="size-5 text-green-600" />
                    WhatsApp linked successfully! Ready to launch.
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )
    }
  }

  const renderFooter = () => {
    if (step === 1) {
      return (
        <Button
          onClick={handleCreateRestaurant}
          disabled={!data.businessName.trim() || loading}
          className="w-full"
          size="lg"
        >
          {loading ? (
            <> <Loader2 className="size-4 mr-2 animate-spin" /> Creating Restaurant... </>
          ) : (
            <> Continue to Delivery Settings <ChevronRight className="size-4 ml-1" /> </>
          )}
        </Button>
      )
    }

    if (step === 2) {
      return (
        <div className="flex gap-3">
          <Button variant="outline" onClick={prevStep} disabled={loading}>
            <ChevronLeft className="size-4 mr-1" /> Back
          </Button>
          <Button onClick={handleSaveDeliverySettings} disabled={loading} className="flex-1">
            {loading ? "Saving..." : "Continue to Menu Upload <ChevronRight className='size-4 ml-1' />"}
          </Button>
        </div>
      )
    }

    if (step === 3) {
      return (
        <div className="flex gap-3">
          <Button variant="outline" onClick={prevStep} disabled={loading}>
            <ChevronLeft className="size-4 mr-1" /> Back
          </Button>
          <Button onClick={handleUploadMenuPdf} disabled={loading} className="flex-1">
            {loading
              ? "Uploading & Indexing..."
              : data.pdfFile
                ? "Upload & Continue <ChevronRight className='size-4 ml-1' />"
                : "Skip for Now <ChevronRight className='size-4 ml-1' />"}
          </Button>
        </div>
      )
    }

    if (step === 4) {
      return (
        <Button variant="outline" onClick={prevStep} disabled={loading || data.whatsAppConnected} className="w-full">
          <ChevronLeft className="size-4 mr-1" /> Back
        </Button>
      )
    }

    return null
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted/50 py-12 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="text-center mb-10">
          <h1 className="text-3xl font-bold tracking-tight">Set Up Your Restaurant</h1>
          <p className="text-muted-foreground mt-2">Complete these 4 steps to launch your AI autopilot</p>
        </div>

        {/* Step Indicator */}
        {renderStepIndicator()}

        {/* Error Toast */}
        {error && (
          <div className="mb-6 flex items-center gap-3 rounded-lg bg-destructive/10 border border-destructive/20 p-4 text-sm text-destructive" role="alert">
            <AlertCircle className="size-5 flex-shrink-0" />
            <span>{error}</span>
            <Button variant="ghost" size="icon" onClick={() => setError(null)} className="ml-auto">
              <X className="size-4" />
            </Button>
          </div>
        )}

        {/* Step Content */}
        <Card className="shadow-sm">
          <CardContent className="pt-6 pb-8">
            {renderStepContent()}
          </CardContent>
          <CardFooter className="border-t pt-4">
            {renderFooter()}
          </CardFooter>
        </Card>

        {/* Progress hint */}
        <p className="text-center text-xs text-muted-foreground mt-6">
          Step {step} of 4
        </p>
      </div>
    </div>
  )
}