import type { Metadata } from "next"

import { CallToAction, MarketingFooter, MarketingHeader, MarketingMain } from "@/components/marketing/shell"
import { JsonLd } from "@/components/seo/json-ld"
import { FAQS } from "@/content/pages"
import { absoluteUrl } from "@/lib/site"

export const metadata: Metadata = {
  title: "FAQ",
  description: "Answers to common questions about Siyaf: how the agent works, Urdu, orders, the free trial, WhatsApp fees and cancelling.",
  alternates: { canonical: "/faq" },
}

const faqPage = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: FAQS.map((f) => ({
    "@type": "Question",
    name: f.q,
    acceptedAnswer: { "@type": "Answer", text: f.a },
  })),
}

const breadcrumbs = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    { "@type": "ListItem", position: 1, name: "Home", item: absoluteUrl("/") },
    { "@type": "ListItem", position: 2, name: "FAQ", item: absoluteUrl("/faq") },
  ],
}

export default function FaqPage() {
  return (
    <MarketingMain>
      <JsonLd data={[faqPage, breadcrumbs]} />
      <MarketingHeader />

      <section className="space-y-3">
        <h1 className="font-display text-3xl font-semibold">Questions owners ask</h1>
      </section>

      <section className="space-y-5">
        {FAQS.map((f) => (
          <div key={f.q} className="space-y-1">
            <h2 className="font-medium">{f.q}</h2>
            <p className="text-muted-foreground">{f.a}</p>
          </div>
        ))}
      </section>

      <CallToAction text="Start a free trial" />
      <MarketingFooter />
    </MarketingMain>
  )
}
