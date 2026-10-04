import type { Metadata } from "next"
import Link from "next/link"

import { CallToAction, MarketingFooter, MarketingHeader, MarketingMain } from "@/components/marketing/shell"
import { JsonLd } from "@/components/seo/json-ld"
import { CHAT_DEFINITION, EXTRA_CHAT_PKR, FAQS, META_FEE_NOTE, PLANS, TRIAL_CHAT_CAP, TRIAL_DAYS } from "@/content/pages"
import { absoluteUrl, SITE_NAME } from "@/lib/site"

export const metadata: Metadata = {
  title: "Pricing",
  description: "Siyaf plans from Rs 2,999 a month, with a 14-day free trial. What an AI chat is, and how WhatsApp fees work.",
  alternates: { canonical: "/pricing" },
}

const software = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: SITE_NAME,
  applicationCategory: "BusinessApplication",
  operatingSystem: "Web",
  url: absoluteUrl("/pricing"),
  offers: PLANS.map((p) => ({
    "@type": "Offer",
    name: p.name,
    price: String(p.priceMonthly),
    priceCurrency: "PKR",
    priceSpecification: { "@type": "UnitPriceSpecification", price: String(p.priceMonthly), priceCurrency: "PKR", unitCode: "MON" },
    description: `${p.chats.toLocaleString()} AI chats a month`,
  })),
}

const breadcrumbs = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    { "@type": "ListItem", position: 1, name: "Home", item: absoluteUrl("/") },
    { "@type": "ListItem", position: 2, name: "Pricing", item: absoluteUrl("/pricing") },
  ],
}

export default function PricingPage() {
  return (
    <MarketingMain>
      <JsonLd data={[software, breadcrumbs]} />
      <MarketingHeader />

      <section className="space-y-3">
        <h1 className="font-display text-3xl font-semibold">Pricing</h1>
        <p className="text-muted-foreground">
          Every plan includes the agent, your menu, orders with customer confirmation, and the owner dashboard. Pay monthly, or
          yearly and get two months free. A {TRIAL_DAYS}-day free trial allows up to {TRIAL_CHAT_CAP} AI chats, and no payment is
          needed to start.
        </p>
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        {PLANS.map((p) => (
          <div key={p.key} className="flex flex-col gap-2 rounded-lg border p-5">
            <h2 className="font-display text-lg font-semibold">{p.name}</h2>
            <p className="font-mono text-2xl tabular-nums">Rs {p.priceMonthly.toLocaleString("en-US")}<span className="text-sm text-muted-foreground"> / month</span></p>
            <p className="text-sm text-muted-foreground">or Rs {p.priceYearly.toLocaleString("en-US")} a year</p>
            <p className="text-sm">{p.chats.toLocaleString("en-US")} AI chats a month</p>
            <p className="text-sm text-muted-foreground">Extra chats are Rs {EXTRA_CHAT_PKR} each.</p>
          </div>
        ))}
      </section>

      <section className="space-y-2">
        <h2 className="font-display text-xl font-semibold">What is an AI chat?</h2>
        <p className="text-muted-foreground">{CHAT_DEFINITION}</p>
      </section>

      <section className="space-y-2">
        <h2 className="font-display text-xl font-semibold">WhatsApp fees</h2>
        <p className="text-muted-foreground">{META_FEE_NOTE}</p>
      </section>

      <section className="space-y-2">
        <h2 className="font-display text-xl font-semibold">Common questions</h2>
        <ul className="space-y-2 text-sm">
          {FAQS.slice(0, 4).map((f) => (
            <li key={f.q}>
              <span className="font-medium">{f.q}</span> {f.a}
            </li>
          ))}
        </ul>
        <p className="text-sm"><Link className="underline underline-offset-4" href="/faq">All questions</Link></p>
      </section>

      <CallToAction text="Start a free trial" />
      <MarketingFooter />
    </MarketingMain>
  )
}
