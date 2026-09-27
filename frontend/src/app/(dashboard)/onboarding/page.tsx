"use client"

import React, { useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { CheckCircle2, ChevronRight, Store, Truck, FileUp, MessageSquareShare } from "lucide-react"
import API from "@/lib/axios-client"

export default function OnboardingPage() {
  const router = useRouter()
  const [step, setStep] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Step 1: Profile
  const [businessName, setBusinessName] = useState("")
  const [businessPhone, setBusinessPhone] = useState("")
  const [address, setAddress] = useState("")
  const [currency, setCurrency] = useState("USD")

  // Step 2: Delivery & Prep
  const [flatDeliveryFee, setFlatDeliveryFee] = useState("2.50")
  const [prepTime, setPrepTime] = useState("30")

  // Step 3: PDF Menu Upload
  const [pdfFile, setPdfFile] = useState<File | null>(null)
  const [menuUploaded, setMenuUploaded] = useState(false)

  // Step 4: Meta WhatsApp Connection
  const [phoneNumberId, setPhoneNumberId] = useState("")
  const [wabaId, setWabaId] = useState("")
  const [whatsAppConnected, setWhatsAppConnected] = useState(false)

  // Created Tenant ID
  const [tenantId, setTenantId] = useState<string | null>(null)

  const handleCreateRestaurant = async () => {
    setError(null)
    setLoading(true)
    try {
      const res = await API.post("/tenant/create", {
        business_name: businessName,
        business_phone: businessPhone,
        address: address,
        currency: currency,
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
        setStep(2)
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
        flat_delivery_fee: parseFloat(flatDeliveryFee) || 0.0,
        avg_prep_time_minutes: parseInt(prepTime) || 30
      })
      setStep(3)
    } catch (err: any) {
      setError("Could not save delivery settings.")
    } finally {
      setLoading(false)
    }
  }

  const handleUploadMenuPdf = async () => {
    if (!pdfFile) {
      setStep(4)
      return
    }

    setLoading(true)
    setError(null)
    try {
      const formData = new FormData()
      formData.append("file", pdfFile)

      const res = await API.post("/tenant/upload-menu-pdf", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      })

      console.log(res)

      if (res.data.status === "success") {
        setMenuUploaded(true)
        setStep(4)
      } else {
        setError(res.data.message || "Failed to index the menu PDF.")
      }
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
        "Failed to upload menu PDF. Please try again."
      )
    } finally {
      setLoading(false)
    }
  }

  const handleMetaEmbeddedSignup = async () => {
    setLoading(true)
    setError(null)
    try {
      // Meta Embedded Signup handshake
      await API.post("/tenant/meta-embedded-signup", {
        code: "embedded_signup_code_dev",
        phone_number_id: phoneNumberId || "109823746501928",
        waba_id: wabaId || "100293847562810"
      })
      setWhatsAppConnected(true)
      setTimeout(() => {
        router.push("/dashboard")
      }, 1200)
    } catch (err: any) {
      setError(err.response?.data?.detail || "Could not link WhatsApp account.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto py-10 px-4">
      {/* Step Indicator */}
      <div className="flex items-center justify-between mb-8 border-b pb-4">
        {[
          { num: 1, label: "Profile", icon: Store },
          { num: 2, label: "Delivery", icon: Truck },
          { num: 3, label: "Menu PDF", icon: FileUp },
          { num: 4, label: "WhatsApp", icon: MessageSquareShare },
        ].map((s) => (
          <div
            key={s.num}
            className={`flex items-center gap-2 ${step === s.num ? "text-primary font-bold" : step > s.num ? "text-green-600 font-medium" : "text-muted-foreground"}`}
          >
            <div className={`size-8 rounded-full flex items-center justify-center text-xs ${step === s.num ? "bg-primary text-primary-foreground" : step > s.num ? "bg-green-100 text-green-700" : "bg-muted"}`}>
              {step > s.num ? <CheckCircle2 className="size-4" /> : s.num}
            </div>
            <span className="hidden sm:inline text-sm">{s.label}</span>
          </div>
        ))}
      </div>

      {error && (
        <div className="mb-6 rounded-md bg-destructive/15 p-3 text-sm text-destructive font-medium">
          {error}
        </div>
      )}

      {/* STEP 1: RESTAURANT PROFILE */}
      {step === 1 && (
        <Card>
          <CardHeader>
            <CardTitle>Welcome! Let's set up your Restaurant</CardTitle>
            <CardDescription>
              Your autonomous AI agent will use these details to introduce your restaurant and converse with customers on WhatsApp.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="bname">Restaurant / Brand Name *</Label>
              <Input
                id="bname"
                placeholder="e.g. Spice Symphony / Lahore Bistro"
                value={businessName}
                onChange={(e) => setBusinessName(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="bphone">Public Contact Phone</Label>
              <Input
                id="bphone"
                placeholder="+1 555-0199 / +92 300 1234567"
                value={businessPhone}
                onChange={(e) => setBusinessPhone(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="baddr">Restaurant Physical Address</Label>
              <Input
                id="baddr"
                placeholder="123 Food Street, Downtown"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="currency">Currency Code</Label>
                <Input
                  id="currency"
                  placeholder="USD, PKR, EUR, GBP"
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                />
              </div>
            </div>
          </CardContent>
          <CardFooter className="flex justify-end">
            <Button
              onClick={handleCreateRestaurant}
              disabled={!businessName.trim() || loading}
            >
              {loading ? "Saving..." : "Continue to Delivery Settings"}
              <ChevronRight className="size-4 ml-1" />
            </Button>
          </CardFooter>
        </Card>
      )}

      {/* STEP 2: DELIVERY & KITCHEN SETTINGS */}
      {step === 2 && (
        <Card>
          <CardHeader>
            <CardTitle>Delivery & Kitchen Times</CardTitle>
            <CardDescription>
              Configure standard delivery charges and prep estimates. The AI agent calculates totals automatically when customers place orders.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="fee">Flat Delivery Fee ({currency})</Label>
              <Input
                id="fee"
                type="number"
                step="0.5"
                value={flatDeliveryFee}
                onChange={(e) => setFlatDeliveryFee(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="prep">Average Prep & Delivery Time (minutes)</Label>
              <Input
                id="prep"
                type="number"
                value={prepTime}
                onChange={(e) => setPrepTime(e.target.value)}
              />
            </div>
          </CardContent>
          <CardFooter className="flex justify-between">
            <Button variant="ghost" onClick={() => setStep(1)}>Back</Button>
            <Button onClick={handleSaveDeliverySettings} disabled={loading}>
              {loading ? "Saving..." : "Continue to Menu Upload"}
              <ChevronRight className="size-4 ml-1" />
            </Button>
          </CardFooter>
        </Card>
      )}

      {/* STEP 3: MENU PDF UPLOAD */}
      {step === 3 && (
        <Card>
          <CardHeader>
            <CardTitle>Upload Menu & Pricing PDF</CardTitle>
            <CardDescription>
              Upload your digital menu or special deals sheet. Our vector RAG engine indexes dish names, ingredients, and prices so the AI never hallucinates.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="border-2 border-dashed rounded-lg p-8 text-center space-y-3">
              <FileUp className="size-10 mx-auto text-muted-foreground" />
              <div>
                <Label htmlFor="pdf" className="cursor-pointer text-primary font-semibold hover:underline">
                  Click to choose a PDF file
                </Label>
                <input
                  id="pdf"
                  type="file"
                  accept=".pdf,application/pdf"
                  className="hidden"
                  onChange={(e) => setPdfFile(e.target.files ? e.target.files[0] : null)}
                />
              </div>
              {pdfFile ? (
                <p className="text-sm font-medium text-green-600">Selected: {pdfFile.name}</p>
              ) : (
                <p className="text-xs text-muted-foreground">PDF menus, price sheets, or store policies</p>
              )}
            </div>
          </CardContent>
          <CardFooter className="flex justify-between">
            <Button variant="ghost" onClick={() => setStep(2)}>Back</Button>
            <Button onClick={handleUploadMenuPdf} disabled={loading}>
              {loading
                ? "Uploading & indexing..."
                : pdfFile
                  ? "Upload & Continue"
                  : "Skip for Now"}
              <ChevronRight className="size-4 ml-1" />
            </Button>
          </CardFooter>
        </Card>
      )}

      {/* STEP 4: META EMBEDDED SIGNUP (WHATSAPP) */}
      {step === 4 && (
        <Card>
          <CardHeader>
            <CardTitle>Connect Your WhatsApp Business Account</CardTitle>
            <CardDescription>
              Connect your official WhatsApp Business number via Meta Embedded Signup. All customer queries and orders will be handled on autopilot.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-lg bg-muted/60 p-4 space-y-2 border">
              <h4 className="font-semibold text-sm flex items-center gap-2">
                <MessageSquareShare className="size-4 text-primary" />
                Meta Embedded Signup Integration
              </h4>
              <p className="text-xs text-muted-foreground">
                In production, clicking the button triggers Meta's secure embedded popup window to authenticate your Meta Business Manager and grant WhatsApp Cloud API permissions.
              </p>
            </div>

            <div className="space-y-3 pt-2">
              <div className="space-y-1.5">
                <Label htmlFor="phoneId">WhatsApp Phone Number ID</Label>
                <Input
                  id="phoneId"
                  placeholder="e.g. 109823746501928"
                  value={phoneNumberId}
                  onChange={(e) => setPhoneNumberId(e.target.value)}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="wabaId">WhatsApp Business Account (WABA) ID</Label>
                <Input
                  id="wabaId"
                  placeholder="e.g. 100293847562810"
                  value={wabaId}
                  onChange={(e) => setWabaId(e.target.value)}
                />
              </div>
            </div>

            {whatsAppConnected && (
              <div className="rounded-md bg-green-50 text-green-800 p-3 text-sm font-medium flex items-center gap-2">
                <CheckCircle2 className="size-5 text-green-600" />
                WhatsApp linked successfully! Launching your Autopilot Dashboard...
              </div>
            )}
          </CardContent>
          <CardFooter className="flex justify-between">
            <Button variant="ghost" onClick={() => setStep(3)}>Back</Button>
            <Button
              onClick={handleMetaEmbeddedSignup}
              disabled={loading || whatsAppConnected}
              className="bg-green-600 hover:bg-green-700 text-white"
            >
              {loading ? "Connecting WhatsApp..." : "Complete Setup & Launch Autopilot"}
            </Button>
          </CardFooter>
        </Card>
      )}
    </div>
  )
}
