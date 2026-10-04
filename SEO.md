# SEO plan for Siyaf

Instructions for Claude Code (sections 2 and 3), plus the founder's checklist (sections 4–6). Read the whole file before starting.

## 1. What to expect

- Siyaf sells to restaurant owners in Pakistan who look for ways to take orders on WhatsApp. That's a small, specific set of searches. Fewer people search, but the ones who do are close to buying.
- SEO takes **3–6 months** to bring steady traffic. Early customers will come from outreach and demos. SEO is the channel that keeps growing after that.
- More and more owners ask ChatGPT or see Google's AI answers instead of clicking results. Pages that answer questions plainly, with clear facts (prices, how it works, what's needed), get quoted there too.
- **Never invent numbers, reviews or customer names** on any page or in structured data. Google penalises fake reviews, and it would hurt trust.

## 2. Technical SEO (build first)

The site address comes from a new environment variable, `NEXT_PUBLIC_SITE_URL` (for example `https://siyaf.com`). Add it to `.env.example` and Vercel. Every absolute URL below is built from it.

### 2.1 Metadata
- In `src/app/layout.tsx`:
  - set `metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL)`
  - a title template: `{ default: "Siyaf: AI WhatsApp ordering for restaurants", template: "%s · Siyaf" }`
  - `openGraph` with `siteName: "Siyaf"`, `locale: "en_PK"`, `type: "website"`
  - `twitter: { card: "summary_large_image" }`
- Every public page exports its own `metadata`: a unique `title` (under 60 characters), a `description` (140–160 characters, saying who it's for and what it does) and `alternates.canonical`.
- `opengraph-image.png` already exists in `src/app/`. Pages with their own topic (pricing, each guide) get their own `opengraph-image.tsx`, generated with `next/og`: the logo, the page title and the brand colours.

### 2.2 Keep private pages out of search
- In `(dashboard)/layout.tsx`, `setup`, `founder/layout.tsx`, `login` and `signup`, export `metadata.robots = { index: false, follow: false }`.
- Add `src/app/robots.ts`:
  - allow `/`
  - disallow `/dashboard`, `/setup`, `/founder` and `/api`
  - point to the sitemap
- Add `src/app/sitemap.ts`: list every public page with `lastModified` and `changeFrequency`, and include the guides automatically from the content folder (2.4).

### 2.3 Structured data (JSON-LD)
Add a small `<JsonLd>` server component that writes `<script type="application/ld+json">`.
- **On every page, `Organization`:** name Siyaf, url, logo (`/brand/logo-light-1024.png`), and `sameAs` with the LinkedIn and X profile URLs.
- **On the home and pricing pages, `SoftwareApplication`:**
  - `applicationCategory: "BusinessApplication"`, `operatingSystem: "Web"`
  - `offers`: the three plans from `PRICING.md` in PKR. Basic 2999, Standard 5999 and Pro 11999, each with `priceCurrency: "PKR"`, a monthly unit, and a `description` with its chat allowance.
  - **No** `aggregateRating` or `review` until there are real reviews.
- **On pages with an FAQ, `FAQPage`:** the questions and answers exactly as shown on the page.
- **On guides, `Article`:** headline, datePublished, dateModified, author (the founder's name), image.
- **On guides and feature pages, `BreadcrumbList`.**

### 2.4 Content pages and guides
- Store guides as MDX in `frontend/content/guides/*.mdx`, rendered with `@next/mdx` (or `next-mdx-remote`) at `/guides/[slug]`.
- Front matter: `title`, `description`, `date`, `updated`, `keywords`.
- Every guide shows the date it was last updated. Guides about Meta's prices must be accurate on that date.
- Each guide ends with a short call to action ("Set up Siyaf in 10 minutes" → `/signup`) and links to 2–3 related pages.

### 2.5 Page experience
- **Text in the HTML:** all public page text is server-rendered. Animations (`LANDING.md`) must not hide text from crawlers. Text that animates in must still be in the HTML at load.
- **Speed targets** on mobile: LCP under 2.5s, CLS under 0.05, INP under 200ms. The hero photo uses `priority`, and fonts use `next/font`.
- **Headings:** one `h1` per page, then headings in order.
- **Alt text:** every image has meaningful `alt` text.
- **Readable links:** internal links use plain words ("WhatsApp ordering for restaurants"), not "click here".

### 2.6 Build order (stop for review after each)
1. 2.1 to 2.3: metadata, robots, sitemap, noindex on private pages, JSON-LD
2. The pages in section 3 that don't exist yet: pricing, how it works, FAQ, and the guides framework with the first guide
3. Run a Lighthouse SEO audit (target 100) and paste each page into Google's Rich Results Test. Fix anything they report.

## 3. Pages to build

Each page targets one kind of search. Write in plain English. Keep the top of each page short and direct, then go into detail below.

| URL | Main search it answers | What's on it |
|---|---|---|
| `/` | WhatsApp ordering for restaurants | The landing page from `LANDING.md` |
| `/pricing` | Siyaf pricing, WhatsApp bot price in Pakistan | The three plans, what a chat is, Meta's fees explained plainly, FAQ |
| `/how-it-works` | how a WhatsApp ordering bot works | The setup steps, a sample conversation, takeover, what owners see |
| `/features/whatsapp-order-taking` | WhatsApp order taking for restaurants | Orders taken in chat, button confirmation, sent to the kitchen |
| `/features/roman-urdu-and-voice-notes` | WhatsApp bot that understands Urdu | Replies in English and Roman Urdu, understanding voice notes |
| `/faq` | questions owners ask | 10–15 real questions, with `FAQPage` data |
| `/guides/whatsapp-business-api-pricing-pakistan` | WhatsApp Business API pricing in Pakistan | Meta's October 2026 change explained: 1,000 free replies, then the per-reply fee, with a worked example for a restaurant. **This is the strongest early guide**, because the change is new and owners are confused. |
| `/guides/take-restaurant-orders-on-whatsapp` | how to take restaurant orders on WhatsApp | Manual vs WhatsApp Business app vs an AI agent, honestly compared |
| `/guides/whatsapp-business-app-vs-api` | WhatsApp Business app vs API | The differences, when a restaurant needs the API, moving a number |
| `/guides/set-up-whatsapp-business-api-restaurant` | how to set up the WhatsApp Business API | Step by step: a Meta account, the number rules, verification |
| `/compare/siyaf-vs-hiring-order-taker` | the cost of an order-taker vs a bot | Salary vs subscription, 24-hour cover, when a person is still better |

**Later, once there are customers:** city pages (`/lahore`, `/karachi`, `/islamabad`), each with genuinely local content such as a real local restaurant's story. Don't make thin copies of the same page with only the city name changed; Google treats those as spam.

**Roman Urdu and Urdu:** once the English pages exist, add Roman Urdu versions of the top three guides, then Urdu-script versions. Owners often search that way. Use `alternates.languages` (hreflang) to link the language versions.

## 4. Keywords to check

Check these in Google Keyword Planner and, after launch, in Search Console. These are starting ideas, not measured numbers.

- **English:**
  - whatsapp ordering system for restaurants
  - whatsapp chatbot for restaurants pakistan
  - restaurant whatsapp automation
  - ai order taking for restaurants
  - whatsapp food ordering bot
  - whatsapp business api pricing pakistan
  - whatsapp business api for restaurants
  - whatsapp auto reply for restaurant
- **Roman Urdu:**
  - whatsapp par order lena
  - restaurant ke liye whatsapp bot
  - whatsapp business api kya hai
- **Urdu:**
  - واٹس ایپ پر آرڈر
  - ریسٹورنٹ کے لیے واٹس ایپ بوٹ

## 5. Founder's checklist (outside the code)

1. **Domain:** buy one (for example `siyaf.com`, `siyaf.pk` or `siyaf.ai`), connect it in Vercel, and set `NEXT_PUBLIC_SITE_URL` and the backend's `FRONTEND_ORIGIN` to it. Update the Google OAuth redirect URIs and the Meta app domain to match.
2. **Google Search Console:** verify the domain (a DNS record) and submit `/sitemap.xml`. Do the same in Bing Webmaster Tools. Bing also feeds ChatGPT search.
3. **Google Business Profile:** create one for Siyaf as a service-area business, if you have a business address. It helps the brand name show up in searches.
4. **Profiles that link back:** LinkedIn company page, X, the GitHub README, Product Hunt at launch, and Pakistani startup directories. Each links to the site and uses the same name, logo and one-line description.
5. **A growth loop:** offer restaurants an "Order on WhatsApp" button and badge for their Instagram, Facebook and website, linking to their WhatsApp chat with a small "powered by Siyaf" link. Each restaurant brings both customers and a backlink.
6. **Analytics:** turn on Vercel Analytics or Plausible. Track sign-ups started and setup finished as goals.

## 6. Every month
- **Search Console:** look at which searches show Siyaf, and which pages get impressions but few clicks. Rewrite those titles and descriptions first.
- **New content:** publish 2 guides a month, each answering a real question an owner asked you.
- **Meta's prices:** update `/pricing` and the API pricing guide whenever Meta changes prices, and update the "last updated" date.
