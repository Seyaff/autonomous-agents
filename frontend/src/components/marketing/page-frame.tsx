import Link from "next/link"

import { CallToAction, MarketingFooter, MarketingHeader, MarketingMain } from "@/components/marketing/shell"
import { JsonLd } from "@/components/seo/json-ld"
import { absoluteUrl } from "@/lib/site"

export type Crumb = { name: string; path: string }

// Breadcrumb trail, shown on the page and in structured data.
export function Breadcrumbs({ crumbs }: { crumbs: Crumb[] }) {
  const data = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: crumbs.map((c, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: c.name,
      item: absoluteUrl(c.path),
    })),
  }
  return (
    <nav aria-label="Breadcrumb" className="text-sm text-muted-foreground">
      <JsonLd data={data} />
      <ol className="flex flex-wrap gap-1">
        {crumbs.map((c, i) => (
          <li key={c.path} className="flex gap-1">
            {i > 0 && <span aria-hidden>/</span>}
            {i < crumbs.length - 1 ? (
              <Link className="underline underline-offset-4" href={c.path}>{c.name}</Link>
            ) : (
              <span>{c.name}</span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  )
}

export function RelatedLinks({ links }: { links: { href: string; label: string }[] }) {
  if (links.length === 0) return null
  return (
    <section className="space-y-2">
      <h2 className="font-display text-xl font-semibold">Related</h2>
      <ul className="list-disc space-y-1 pl-5 text-sm">
        {links.map((l) => (
          <li key={l.href}>
            <Link className="underline underline-offset-4" href={l.href}>{l.label}</Link>
          </li>
        ))}
      </ul>
    </section>
  )
}

// Shared frame for public marketing pages: header, breadcrumbs, the page's own content, a call to action, and the footer.
export function PublicPage({
  crumbs,
  children,
  structured,
  cta = "Start a free trial",
  ctaHref = "/signup",
}: {
  crumbs: Crumb[]
  children: React.ReactNode
  structured?: Record<string, unknown>[]
  cta?: string
  ctaHref?: string
}) {
  return (
    <MarketingMain>
      {structured && <JsonLd data={structured} />}
      <MarketingHeader />
      <Breadcrumbs crumbs={crumbs} />
      {children}
      <CallToAction text={cta} href={ctaHref} />
      <MarketingFooter />
    </MarketingMain>
  )
}
