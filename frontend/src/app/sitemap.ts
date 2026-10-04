import type { MetadataRoute } from "next"
import { FEATURES } from "@/content/features"
import { PUBLISHED_GUIDES } from "@/content/guides"
import { absoluteUrl } from "@/lib/site"

// Every public page. New guides and feature pages are added here automatically from their content files.
export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date()
  const fixed: MetadataRoute.Sitemap = [
    { url: absoluteUrl("/"), lastModified: now, changeFrequency: "weekly", priority: 1 },
    { url: absoluteUrl("/pricing"), lastModified: now, changeFrequency: "monthly", priority: 0.9 },
    { url: absoluteUrl("/how-it-works"), lastModified: now, changeFrequency: "monthly", priority: 0.8 },
    { url: absoluteUrl("/faq"), lastModified: now, changeFrequency: "monthly", priority: 0.7 },
    { url: absoluteUrl("/guides"), lastModified: now, changeFrequency: "weekly", priority: 0.7 },
    { url: absoluteUrl("/compare/siyaf-vs-hiring-order-taker"), lastModified: now, changeFrequency: "monthly", priority: 0.6 },
    { url: absoluteUrl("/privacy"), lastModified: now, changeFrequency: "yearly", priority: 0.3 },
    { url: absoluteUrl("/terms"), lastModified: now, changeFrequency: "yearly", priority: 0.3 },
  ]
  const features = FEATURES.map((f) => ({
    url: absoluteUrl(`/features/${f.slug}`),
    lastModified: now,
    changeFrequency: "monthly" as const,
    priority: 0.7,
  }))
  const guides = PUBLISHED_GUIDES.map((g) => ({
    url: absoluteUrl(`/guides/${g.slug}`),
    lastModified: new Date(g.updated),
    changeFrequency: "monthly" as const,
    priority: 0.8,
  }))
  return [...fixed, ...features, ...guides]
}
