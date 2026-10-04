import type { Metadata } from "next"

import { CallToAction, MarketingFooter, MarketingHeader, MarketingMain } from "@/components/marketing/shell"
import { JsonLd } from "@/components/seo/json-ld"
import { absoluteUrl } from "@/lib/site"

export const metadata: Metadata = {
  title: "How it works",
  description: "How a WhatsApp ordering agent works for a restaurant: setup, a sample conversation, order confirmation, and taking over a chat.",
  alternates: { canonical: "/how-it-works" },
}

const breadcrumbs = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    { "@type": "ListItem", position: 1, name: "Home", item: absoluteUrl("/") },
    { "@type": "ListItem", position: 2, name: "How it works", item: absoluteUrl("/how-it-works") },
  ],
}

const steps = [
  { title: "Add your restaurant", text: "Your name, opening hours, delivery areas and payment methods." },
  { title: "Upload your menu", text: "A PDF or a list of dishes. Check the dish list, and hide or sell out anything that's off." },
  { title: "Connect WhatsApp", text: "Connect your number through Meta, or enter its details. Customers can reach the agent once it's connected." },
  { title: "Go live", text: "The agent starts answering. You see every chat and every order on the dashboard." },
]

export default function HowItWorksPage() {
  return (
    <MarketingMain>
      <JsonLd data={breadcrumbs} />
      <MarketingHeader />

      <section className="space-y-3">
        <h1 className="font-display text-3xl font-semibold">How a WhatsApp ordering agent works</h1>
        <p className="text-muted-foreground">
          Siyaf answers your customers on WhatsApp. Here is the setup, a sample conversation, and what you see.
        </p>
      </section>

      <section className="space-y-4">
        <h2 className="font-display text-xl font-semibold">Setup in four steps</h2>
        <ol className="list-decimal space-y-3 pl-5">
          {steps.map((s) => (
            <li key={s.title}>
              <span className="font-medium">{s.title}.</span> <span className="text-muted-foreground">{s.text}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="space-y-3">
        <h2 className="font-display text-xl font-semibold">A sample conversation</h2>
        <p className="text-sm text-muted-foreground">An illustrative example. The dishes and prices are made up.</p>
        <div className="space-y-2 rounded-lg border p-4 text-sm">
          <p><span className="font-medium">Customer:</span> Salam, kya menu hai?</p>
          <p><span className="font-medium">Agent:</span> Salam! Mains mein Chicken Karahi (Rs 1,200) aur Chicken Biryani (Rs 450) hain. Kya order krna hai?</p>
          <p><span className="font-medium">Customer:</span> Biryani 2 plate, Gulberg, cash.</p>
          <p><span className="font-medium">Agent:</span> Summary: 2 x Chicken Biryani, Gulberg, cash on delivery. Confirm karein?</p>
          <p><span className="font-medium">Customer:</span> Confirm.</p>
          <p><span className="font-medium">Agent:</span> Order confirm ho gaya. Shukriya!</p>
        </div>
        <p className="text-sm text-muted-foreground">The order goes to your kitchen only after the customer taps Confirm.</p>
      </section>

      <section className="space-y-2">
        <h2 className="font-display text-xl font-semibold">You stay in charge</h2>
        <p className="text-muted-foreground">
          Take over any chat and reply yourself, then hand it back to the agent. A refund or a complaint goes to you as an alert.
        </p>
      </section>

      <CallToAction text="Start a free trial" />
      <MarketingFooter />
    </MarketingMain>
  )
}
