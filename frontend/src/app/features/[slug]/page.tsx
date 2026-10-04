import type { Metadata } from "next"
import { notFound } from "next/navigation"

import { PublicPage } from "@/components/marketing/page-frame"
import { FEATURES, featureBySlug } from "@/content/features"
import { absoluteUrl } from "@/lib/site"

type Params = { params: Promise<{ slug: string }> }

export function generateStaticParams() {
  return FEATURES.map((f) => ({ slug: f.slug }))
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params
  const feature = featureBySlug(slug)
  if (!feature) return {}
  return {
    title: feature.title,
    description: feature.description,
    alternates: { canonical: `/features/${feature.slug}` },
  }
}

export default async function FeaturePage({ params }: Params) {
  const { slug } = await params
  const feature = featureBySlug(slug)
  if (!feature) notFound()

  const path = `/features/${feature.slug}`
  const breadcrumbs = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: absoluteUrl("/") },
      { "@type": "ListItem", position: 2, name: feature.heading, item: absoluteUrl(path) },
    ],
  }

  return (
    <PublicPage
      crumbs={[{ name: "Home", path: "/" }, { name: feature.heading, path }]}
      structured={[breadcrumbs]}
    >
      <section className="space-y-3">
        <h1 className="font-display text-3xl font-semibold">{feature.heading}</h1>
        <p className="text-muted-foreground">{feature.intro}</p>
      </section>

      <section className="space-y-5">
        {feature.points.map((p) => (
          <div key={p.title} className="space-y-1">
            <h2 className="font-display text-xl font-semibold">{p.title}</h2>
            <p className="text-muted-foreground">{p.text}</p>
          </div>
        ))}
      </section>
    </PublicPage>
  )
}
