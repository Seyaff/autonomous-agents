import type { Metadata } from "next"
import Link from "next/link"

import { PublicPage } from "@/components/marketing/page-frame"
import { PLANS } from "@/content/pages"

export const metadata: Metadata = {
  title: "Siyaf vs hiring an order-taker",
  description: "Comparing a monthly Siyaf plan with hiring a person to take WhatsApp orders: cost, cover hours, and when a person is still the better choice.",
  alternates: { canonical: "/compare/siyaf-vs-hiring-order-taker" },
}

const rows = [
  { label: "Monthly cost", person: "Salary, plus any benefits and time off", siyaf: `From Rs ${PLANS[0].priceMonthly.toLocaleString("en-US")} a month, plus WhatsApp fees billed by Meta` },
  { label: "Hours covered", person: "Their shift", siyaf: "Every hour, including late evenings and holidays" },
  { label: "Busy times", person: "One reply at a time", siyaf: "Several conversations at once" },
  { label: "Your control", person: "Trained and supervised by you", siyaf: "Your menu and rules. You can take over any chat" },
  { label: "Handling a complaint", person: "Stays with the person", siyaf: "Passed to you as an alert" },
]

export default function CompareOrderTakerPage() {
  return (
    <PublicPage crumbs={[{ name: "Home", path: "/" }, { name: "Siyaf vs hiring an order-taker", path: "/compare/siyaf-vs-hiring-order-taker" }]}>
      <section className="space-y-3">
        <h1 className="font-display text-3xl font-semibold">Siyaf or an order-taker?</h1>
        <p className="text-muted-foreground">
          A person costs a salary every month and works set hours. Siyaf costs a monthly plan and answers every hour. Here is how
          they compare.
        </p>
      </section>

      <section className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b">
              <th className="py-2 pr-4 font-medium" />
              <th className="py-2 pr-4 font-medium">Order-taker</th>
              <th className="py-2 font-medium">Siyaf</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.label} className="border-b align-top">
                <th scope="row" className="py-2 pr-4 font-medium">{r.label}</th>
                <td className="py-2 pr-4 text-muted-foreground">{r.person}</td>
                <td className="py-2 text-muted-foreground">{r.siyaf}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="space-y-2">
        <h2 className="font-display text-xl font-semibold">Compare your own numbers</h2>
        <p className="text-muted-foreground">
          Take the monthly salary and benefits you pay now, and set them against the plan you&apos;d choose. The Basic plan is the
          lowest-cost option. WhatsApp message fees are billed by Meta separately, on top of the plan.
        </p>
        <p className="text-sm">
          <Link className="underline underline-offset-4" href="/pricing">See the plans</Link>
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="font-display text-xl font-semibold">When a person is still the better choice</h2>
        <p className="text-muted-foreground">
          A person handles things a bot shouldn&apos;t: a difficult complaint, a custom event order, or a regular customer who wants to
          talk. Many restaurants use both, with the agent taking routine orders and a person handling the rest.
        </p>
      </section>
    </PublicPage>
  )
}
