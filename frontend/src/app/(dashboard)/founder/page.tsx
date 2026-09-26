"use client"

import React, { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  Search,
  Sparkles,
  Download,
  Flame,
  Send,
  Mail,
  MessageSquare,
  Building,
  CheckCircle,
  BellRing
} from "lucide-react"
import API from "@/lib/axios-client"

interface Lead {
  company_name: string
  tier: "HOT" | "WARM" | "PREMIUM"
  website?: string
  phone?: string
  email?: string
  rating?: number
  review_count?: number
  fit_reason?: string
  recommended_pitch_angle?: string
}

export default function FounderPage() {
  const [query, setQuery] = useState("Scrape top real estate agencies in Miami, Florida and analyze their customer response times")
  const [hunting, setHunting] = useState(false)
  const [campaign, setCampaign] = useState<any>(null)
  const [leads, setLeads] = useState<Lead[]>([])
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null)
  const [pitch, setPitch] = useState<any>(null)
  const [pitchLoading, setPitchLoading] = useState(false)
  const [replyInput, setReplyInput] = useState("Hey, sounds interesting. Can you send over a 2-min demo or calendar link?")
  const [replyAnalysis, setReplyAnalysis] = useState<any>(null)
  const [analyzingReply, setAnalyzingReply] = useState(false)

  const handleStartLeadHunt = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return

    setHunting(true)
    setLeads([])
    setCampaign(null)

    try {
      const res = await API.post("/founder/lead-hunt", {
        query,
        max_leads: 12
      })
      setCampaign(res.data)
      setLeads(res.data.leads || [])
    } catch (err: any) {
      console.error("Lead hunt failed:", err)
    } finally {
      setHunting(false)
    }
  }

  const handleDraftPitch = async (lead: Lead) => {
    setSelectedLead(lead)
    setPitch(null)
    setPitchLoading(true)
    try {
      const res = await API.post("/founder/outreach/draft", {
        company_name: lead.company_name,
        website: lead.website,
        fit_reason: lead.fit_reason,
        recommended_pitch_angle: lead.recommended_pitch_angle
      })
      setPitch(res.data.pitch)
    } catch (err: any) {
      console.error("Pitch generation failed:", err)
    } finally {
      setPitchLoading(false)
    }
  }

  const handleSimulateReply = async () => {
    if (!replyInput.trim()) return
    setAnalyzingReply(true)
    try {
      const res = await API.post("/founder/reply-handler", {
        sender: "+1-305-555-0199",
        message: replyInput,
        founder_whatsapp: "+1234567890"
      })
      setReplyAnalysis(res.data.analysis)
    } catch (err: any) {
      console.error("Reply handler failed:", err)
    } finally {
      setAnalyzingReply(false)
    }
  }

  const getTierBadge = (tier: string) => {
    switch (tier?.toUpperCase()) {
      case "HOT":
        return <Badge className="bg-red-500 hover:bg-red-600 text-white flex items-center gap-1"><Flame className="size-3" /> HOT</Badge>
      case "PREMIUM":
        return <Badge className="bg-amber-500 hover:bg-amber-600 text-white">PREMIUM</Badge>
      case "WARM":
        return <Badge className="bg-blue-500 hover:bg-blue-600 text-white">WARM</Badge>
      default:
        return <Badge variant="outline">{tier}</Badge>
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="border-b pb-4">
        <h1 className="text-3xl font-bold tracking-tight">Founder Growth Engine</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Autonomous Lead Generation (Apify + Tavily), Scoring, Excel Export, and Cold Outreach on Autopilot.
        </p>
      </div>

      {/* SEARCH / PROMPT INPUT */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Sparkles className="size-5 text-primary" />
            Autonomous Lead Generation Agent
          </CardTitle>
          <CardDescription>
            Give the agent any target market or industry. It will scrape data, analyze their bottlenecks, categorize leads into Hot/Warm/Premium tiers, and export to Excel.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleStartLeadHunt} className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-3 size-4 text-muted-foreground" />
              <Input
                className="pl-9"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g. Scrape real-estate agencies in Miami, Florida and categorize by response volume"
                disabled={hunting}
              />
            </div>
            <Button type="submit" disabled={hunting || !query.trim()}>
              {hunting ? "Scraping & Analyzing..." : "Run Lead Hunt"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* CAMPAIGN METRICS & EXPORT BUTTON */}
      {campaign && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Total Scraped</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{campaign.total_leads}</div>
              <p className="text-xs text-muted-foreground mt-1">Businesses analyzed</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-red-600">Hot Leads</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-600">{campaign.breakdown?.hot || 0}</div>
              <p className="text-xs text-muted-foreground mt-1">Highest purchase intent</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-amber-600">Premium Leads</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-amber-600">{campaign.breakdown?.premium || 0}</div>
              <p className="text-xs text-muted-foreground mt-1">Multi-location / High volume</p>
            </CardContent>
          </Card>
          <Card className="flex flex-col justify-center items-center p-4">
            <a
              href={`http://localhost:8000/api/v1/founder/campaigns/${campaign.campaign_id}/export`}
              target="_blank"
              rel="noreferrer"
              className="w-full"
            >
              <Button variant="default" className="w-full bg-green-700 hover:bg-green-800 text-white">
                <Download className="size-4 mr-2" />
                Download Excel (.xlsx)
              </Button>
            </a>
            <p className="text-xs text-muted-foreground mt-1.5 text-center">Ready for spreadsheet CRM import</p>
          </Card>
        </div>
      )}

      {/* LEADS TABLE */}
      {leads.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Qualified Leads</CardTitle>
            <CardDescription>
              Ranked by urgent need for our autonomous WhatsApp customer support agent.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs uppercase bg-muted/50 border-b">
                  <tr>
                    <th className="px-4 py-3">Company</th>
                    <th className="px-4 py-3">Tier</th>
                    <th className="px-4 py-3">Rating</th>
                    <th className="px-4 py-3">Fit Reason</th>
                    <th className="px-4 py-3">Recommended Pitch Angle</th>
                    <th className="px-4 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {leads.map((lead, idx) => (
                    <tr key={idx} className="hover:bg-muted/20">
                      <td className="px-4 py-3 font-semibold">
                        <div>{lead.company_name}</div>
                        <div className="text-xs font-normal text-muted-foreground">{lead.website || lead.phone || lead.email}</div>
                      </td>
                      <td className="px-4 py-3">{getTierBadge(lead.tier)}</td>
                      <td className="px-4 py-3 text-xs">
                        {lead.rating ? `⭐ ${lead.rating} (${lead.review_count || 0})` : "-"}
                      </td>
                      <td className="px-4 py-3 text-xs max-w-xs">{lead.fit_reason || "-"}</td>
                      <td className="px-4 py-3 text-xs max-w-xs font-medium text-foreground">{lead.recommended_pitch_angle || "-"}</td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          size="xs"
                          variant="outline"
                          onClick={() => handleDraftPitch(lead)}
                        >
                          Draft Pitch
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* PERSONALIZED PITCH PREVIEW */}
      {selectedLead && (
        <Card className="border-primary/30">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mail className="size-5 text-primary" />
              Tailored Cold Outreach for {selectedLead.company_name}
            </CardTitle>
            <CardDescription>
              Synthesized by the Cold Outreach Agent using the business's specific pain points and target tier.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {pitchLoading ? (
              <div className="py-6 text-center text-muted-foreground">Drafting personalized multi-channel pitch...</div>
            ) : pitch ? (
              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-lg border p-4 bg-muted/30 space-y-2">
                  <div className="flex items-center gap-1.5 font-semibold text-xs text-primary">
                    <Mail className="size-4" /> Cold Email Pitch
                  </div>
                  <div className="text-xs font-medium">Subject: <span className="text-foreground">{pitch.email_subject}</span></div>
                  <div className="text-xs whitespace-pre-wrap text-muted-foreground bg-background p-3 rounded-md border">
                    {pitch.email_body}
                  </div>
                </div>

                <div className="rounded-lg border p-4 bg-muted/30 space-y-2">
                  <div className="flex items-center gap-1.5 font-semibold text-xs text-green-600">
                    <MessageSquare className="size-4" /> WhatsApp Outreach
                  </div>
                  <div className="text-xs whitespace-pre-wrap text-muted-foreground bg-background p-3 rounded-md border">
                    {pitch.whatsapp_message}
                  </div>
                  <div className="pt-2 flex justify-end">
                    <Button size="xs" className="bg-green-600 hover:bg-green-700 text-white">
                      <Send className="size-3 mr-1" /> Send via Founder WhatsApp
                    </Button>
                  </div>
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>
      )}

      {/* AUTONOMOUS REPLY LISTENER & FOUNDER ALERTS */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BellRing className="size-5 text-amber-500" />
            Autonomous Reply Listener & Founder Notification Simulator
          </CardTitle>
          <CardDescription>
            When prospects reply to your cold email or WhatsApp message, the agent classifies intent, drafts objection handling, and triggers a real-time WhatsApp alert to you.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-3">
            <Input
              value={replyInput}
              onChange={(e) => setReplyInput(e.target.value)}
              placeholder="Simulate an incoming message from a prospect..."
            />
            <Button onClick={handleSimulateReply} disabled={analyzingReply}>
              {analyzingReply ? "Analyzing..." : "Process Inbound Reply"}
            </Button>
          </div>

          {replyAnalysis && (
            <div className="rounded-lg border bg-amber-50/50 p-4 border-amber-200 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-sm text-amber-900">
                  Detected Intent: <Badge className="ml-1 bg-amber-600">{replyAnalysis.intent}</Badge>
                </span>
                {replyAnalysis.notify_founder && (
                  <Badge variant="destructive" className="animate-pulse">
                    ⚡ High-Priority Founder Alert Triggered
                  </Badge>
                )}
              </div>
              <p className="text-xs text-amber-950 font-medium">Founder Summary: {replyAnalysis.founder_summary}</p>
              <div className="mt-2 text-xs bg-white p-3 rounded border text-foreground">
                <span className="font-semibold text-muted-foreground block mb-1">Autonomous Follow-up Response:</span>
                {replyAnalysis.suggested_response}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
