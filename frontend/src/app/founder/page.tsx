"use client"

import * as React from "react"
import { toast } from "sonner"
import { DownloadIcon, Loader2Icon, SearchIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { useHuntLeads } from "@/hooks/founder/use-hunt-leads"
import { useCampaigns } from "@/hooks/founder/use-campaigns"
import { getCampaignExportPath } from "@/services/founder/founder.service"

export default function FounderPage() {
  const [query, setQuery] = React.useState("")
  const [maxLeads, setMaxLeads] = React.useState(15)

  const { mutate: hunt, isPending } = useHuntLeads()
  const { data: campaigns, isLoading: campaignsLoading } = useCampaigns()

  function handleHunt(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = query.trim()
    if (!trimmed || isPending) return

    hunt(
      { query: trimmed, maxLeads },
      {
        onSuccess: (result) => {
          toast.success(
            `Found ${result.total_leads} leads (${result.breakdown.hot} hot, ${result.breakdown.warm} warm, ${result.breakdown.premium} premium)`
          )
          setQuery("")
        },
      }
    )
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">
          Lead generation
        </h1>
        <p className="text-sm text-muted-foreground">
          Prompt your growth agent to find and qualify leads. Each run
          produces a scored campaign you can review and export.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Hunt for leads</CardTitle>
          <CardDescription>
            Describe who you&apos;re targeting — the agent searches, scores,
            and tiers them into Hot / Warm / Premium.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleHunt} className="flex flex-col gap-4">
            <Textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. Scrape top real estate agencies in Florida and analyze their customer response"
              rows={3}
              disabled={isPending}
            />
            <div className="flex items-end gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="maxLeads" className="text-xs">
                  Max leads
                </Label>
                <Input
                  id="maxLeads"
                  type="number"
                  min={5}
                  max={50}
                  value={maxLeads}
                  onChange={(e) => setMaxLeads(Number(e.target.value) || 15)}
                  className="w-24"
                  disabled={isPending}
                />
              </div>
              <Button
                type="submit"
                disabled={!query.trim() || isPending}
                className="gap-2"
              >
                {isPending ? (
                  <Loader2Icon className="size-4 animate-spin" />
                ) : (
                  <SearchIcon className="size-4" />
                )}
                {isPending ? "Hunting..." : "Hunt leads"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold tracking-wide text-muted-foreground uppercase">
          Campaigns
        </h2>

        {campaignsLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : !campaigns || campaigns.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No campaigns yet — run your first lead hunt above.
          </p>
        ) : (
          <div className="flex flex-col gap-2">
            {campaigns.map((c) => (
              <Card key={c.campaign_id}>
                <CardContent className="flex items-center justify-between gap-4 p-4">
                  <div className="flex min-w-0 flex-col gap-1">
                    <p className="truncate text-sm font-medium">{c.query}</p>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span>{c.total_leads} leads</span>
                      <span>·</span>
                      <span>{new Date(c.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Badge
                      variant="outline"
                      className="border-transparent bg-(--status-danger-bg) text-(--status-danger-fg)"
                    >
                      {c.hot_count} hot
                    </Badge>
                    <Badge
                      variant="outline"
                      className="border-transparent bg-(--status-warning-bg) text-(--status-warning-fg)"
                    >
                      {c.warm_count} warm
                    </Badge>
                    <Badge
                      variant="outline"
                      className="border-transparent bg-(--status-info-bg) text-(--status-info-fg)"
                    >
                      {c.premium_count} premium
                    </Badge>
                    <Button
                      variant="ghost"
                      size="icon"
                      render={
                        <a
                          href={getCampaignExportPath(c.campaign_id)}
                          target="_blank"
                          rel="noreferrer"
                        />
                      }
                    >
                      <DownloadIcon className="size-4" />
                      <span className="sr-only">Download Excel</span>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
