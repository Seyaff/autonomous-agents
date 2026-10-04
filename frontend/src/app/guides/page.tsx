import type { Metadata } from "next"
import Link from "next/link"

import { PublicPage } from "@/components/marketing/page-frame"
import { GUIDES } from "@/content/guides"

export const metadata: Metadata = {
  title: "Guides",
  description: "Plain guides for restaurant owners in Pakistan on WhatsApp ordering, WhatsApp Business API pricing, and setup.",
  alternates: { canonical: "/guides" },
}

export default function GuidesIndexPage() {
  return (
    <PublicPage crumbs={[{ name: "Home", path: "/" }, { name: "Guides", path: "/guides" }]}>
      <section className="space-y-3">
        <h1 className="font-display text-3xl font-semibold">Guides for restaurant owners</h1>
        <p className="text-muted-foreground">Short, plain answers to the questions owners ask about WhatsApp ordering and fees.</p>
      </section>

      <ul className="space-y-5">
        {GUIDES.map((g) => (
          <li key={g.slug} className="space-y-1">
            <Link className="font-medium underline underline-offset-4" href={`/guides/${g.slug}`}>{g.title}</Link>
            <p className="text-sm text-muted-foreground">{g.description}</p>
            <p className="text-xs text-muted-foreground">Last updated {g.updated}</p>
          </li>
        ))}
      </ul>
    </PublicPage>
  )
}
