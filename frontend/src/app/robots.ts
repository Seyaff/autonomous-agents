import type { MetadataRoute } from "next"
import { absoluteUrl } from "@/lib/site"

// Public pages are open to search engines. The app's private pages are not.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/dashboard", "/setup", "/founder", "/api"],
    },
    sitemap: absoluteUrl("/sitemap.xml"),
  }
}
