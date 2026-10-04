// Every absolute URL on the site is built from NEXT_PUBLIC_SITE_URL (for example https://siyaf.com).
// Until a domain is set, it falls back to the Vercel address so builds never fail.
export const SITE_NAME = "Siyaf"
const FALLBACK_SITE_URL = "https://siyaf.vercel.app"

export function siteUrl(): string {
  const raw = process.env.NEXT_PUBLIC_SITE_URL || FALLBACK_SITE_URL
  return raw.replace(/\/+$/, "")
}

export function absoluteUrl(path: string): string {
  return `${siteUrl()}${path.startsWith("/") ? path : `/${path}`}`
}
