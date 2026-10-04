import type { Metadata } from "next"
import Link from "next/link"
import { notFound } from "next/navigation"

import { PublicPage, RelatedLinks } from "@/components/marketing/page-frame"
import { FEATURES } from "@/content/features"
import { GUIDES, guideBySlug } from "@/content/guides"
import { absoluteUrl, SITE_NAME } from "@/lib/site"

type Params = { params: Promise<{ slug: string }> }

export function generateStaticParams() {
  return GUIDES.map((g) => ({ slug: g.slug }))
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params
  const guide = guideBySlug(slug)
  if (!guide) return {}
  return {
    title: guide.title,
    description: guide.description,
    keywords: guide.keywords,
    alternates: { canonical: `/guides/${guide.slug}` },
    openGraph: { title: guide.title, description: guide.description, type: "article" },
  }
}

export default async function GuidePage({ params }: Params) {
  const { slug } = await params
  const guide = guideBySlug(slug)
  if (!guide) notFound()

  const path = `/guides/${guide.slug}`
  const article = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: guide.title,
    description: guide.description,
    datePublished: guide.date,
    dateModified: guide.updated,
    // Attributed to the company until the founder's name is added to the site.
    author: { "@type": "Organization", name: SITE_NAME, url: absoluteUrl("/") },
    publisher: { "@type": "Organization", name: SITE_NAME, logo: { "@type": "ImageObject", url: absoluteUrl("/brand/logo-light-1024.png") } },
    image: absoluteUrl(`${path}/opengraph-image`),
    mainEntityOfPage: absoluteUrl(path),
  }

  const related = [
    ...guide.related.map((r) => {
      const g = guideBySlug(r)
      return g ? { href: `/guides/${g.slug}`, label: g.title } : null
    }),
    { href: `/features/${FEATURES[0].slug}`, label: FEATURES[0].title },
  ].filter((x): x is { href: string; label: string } => x !== null)

  return (
    <PublicPage
      crumbs={[
        { name: "Home", path: "/" },
        { name: "Guides", path: "/guides" },
        { name: guide.title, path },
      ]}
      structured={[article]}
      cta="Set up Siyaf in 10 minutes"
      ctaHref="/signup"
    >
      <article className="space-y-8">
        <header className="space-y-3">
          <h1 className="font-display text-3xl font-semibold">{guide.title}</h1>
          <p className="text-sm text-muted-foreground">
            Published {guide.date}. Last updated {guide.updated}.
          </p>
          <p className="text-muted-foreground">{guide.intro}</p>
        </header>

        {guide.sections.map((s) => (
          <section key={s.heading} className="space-y-2">
            <h2 className="font-display text-xl font-semibold">{s.heading}</h2>
            {s.body.map((p) => (
              <p key={p}>{p}</p>
            ))}
          </section>
        ))}
      </article>

      <RelatedLinks links={related} />
      <p className="text-sm">
        <Link className="underline underline-offset-4" href="/guides">All guides</Link>
      </p>
    </PublicPage>
  )
}
