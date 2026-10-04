# Task: Build the Siyaf landing page

Instructions for Claude Code. Read this whole file before starting.

Siyaf's public landing page at `/`: a scroll-driven story in the style of Awwwards-winning pages. It uses real sky photography, GSAP scroll choreography, Framer Motion micro-interactions, and one real 3D object.

**Visual reference:** a light, airy page with a real blue sky and clouds, a huge white headline, and a glossy glass 3D object turning behind it. A rough HTML sketch of the hero is at https://claude.ai/artifact/36oVJk4FnJokZLhQnSAV4f. Use it for composition only. Its sky and hills are vector placeholders, and this build replaces them with real photographs.

---

## Before you start

1. Read `frontend/AGENTS.md`. This is Next.js 16, so check `node_modules/next/dist/docs/` before using routing, image or font APIs.
2. Read `frontend/DESIGN.md` for the brand tokens. The landing page keeps the same fonts for UI text, but has its own light, photographic world (see "Look").
3. Work on a new branch, `feat/landing`.

## Libraries

Install these in `frontend/`:

| Package | Used for |
|---|---|
| `gsap` and `@gsap/react` | ScrollTrigger pinning and scrubbing, SplitText headline reveals, timelines. Use the `useGSAP` hook for cleanup. |
| `lenis` | Smooth scrolling, synced to ScrollTrigger (`lenis.on('scroll', ScrollTrigger.update)` and `gsap.ticker`) |
| `motion` (Framer Motion) | Hover, tap and enter animations on buttons, cards and the nav. Use `motion/react`. |
| `three`, `@react-three/fiber`, `@react-three/drei` | The 3D glass chat bubble, using drei's `MeshTransmissionMaterial` for real refraction |

Rules:
- Every animated component is a client component (`"use client"`). The page shell and text stay server-rendered, so the copy is in the HTML for SEO.
- Register GSAP plugins once, in a single client module.
- Load the 3D canvas with `next/dynamic` and `ssr: false`, after the hero text has painted.

## Routing

- `/` shows the landing page to logged-out visitors. In `src/components/providers/auth-provider.tsx`, add `/` to the public paths. Logged-in owners still go straight to `/dashboard` (or `/setup/...`), and founders to `/founder`, exactly as today.
- Delete the spinner placeholder in `src/app/page.tsx` and render the landing page there.
- Put landing components in `src/components/landing/`.

---

## Assets (real photography)

Download free-licence photos from **Unsplash** or **Pexels** (both allow commercial use without attribution) into `frontend/public/landing/`. Export them as AVIF with a WebP fallback through `next/image`.

| File | What to find | Search terms |
|---|---|---|
| `sky-day.jpg` | Bright blue sky with big, soft white cumulus clouds, no horizon or a very low one, lots of empty sky in the middle for the headline | "blue sky cumulus clouds", "summer sky clouds" |
| `sky-night.jpg` | Deep blue night sky, a few stars, a faint cloud | "night sky clouds blue", "starry sky dark blue" |
| `sky-dawn.jpg` | Soft pink-to-blue dawn sky with clouds | "dawn sky pastel clouds" |
| `sky-sunset.jpg` | Warm golden sunset sky | "golden hour sky clouds" |
| `cloud-1.png` … `cloud-3.png` | Isolated clouds on a transparent background, for parallax layers | "cloud png transparent" (Pexels and Unsplash rarely have these; use a free-licence PNG source, or cut clouds from the day photo) |
| `kitchen.jpg` | A busy South Asian restaurant kitchen or food pass, warm light | "restaurant kitchen night", "biryani kitchen", "chef plating" |
| `food-1.jpg` … `food-3.jpg` | Biryani, karahi, a zinger burger: overhead, appetising | "biryani top view", "karahi", "burger fries" |

- Keep every photo's licence page URL in `frontend/public/landing/CREDITS.md`.
- **Hero size budget:** under 250 KB (AVIF). Give the hero `priority` and a blur placeholder.
- **Optional:** a 6–10 second looping sky time-lapse (Pexels Videos), MP4 and WebM under 2 MB, used instead of `sky-day.jpg` on desktop. Keep the still photo as its poster.
- **Logo:** the founder's portrait in `brand/portrait-draft.jpg` (512px). Copy it into `public/brand/` and use it for the nav, footer and chapter 5. A final version with a button-up shirt will replace it at the same path later.

---

## Look

- **Light and photographic.** Real sky behind everything at the top. White text with soft shadows on the photos. A clean off-white page (`#f6faff`) once the story moves past the sky.
- **Type:**
  - Geist (already in the app) for UI and body text
  - **Instrument Serif italic** for the small storytelling lines ("– your WhatsApp, answered –")
  - the headline "Siyaf" in Geist 500, 18–20vw, tracking -0.05em
- **Accent:** one blue, `#1f6fd6`. Status colors only inside product mock-ups, matching the dashboard.
- **No illustrations.** Real photography, real product UI and the one 3D object only.

---

## The story (scroll choreography)

Each chapter is one section. "Pin" means a GSAP ScrollTrigger pin with `scrub`. Scroll lengths below are percentages of the viewport height.

### 1. Hero: "Your WhatsApp, answered"
- **Shown:** the full-bleed `sky-day` photo, with 2–3 cloud PNG layers in front.
- **Copy:** small italic "– your WhatsApp, answered –", the huge **Siyaf**, one line ("An AI that answers your restaurant's WhatsApp, takes orders and sends them to your kitchen. Day and night."), then "Start free trial" and "See how it works".
- **3D:** behind the headline, a glass chat bubble with three typing dots (`MeshTransmissionMaterial`, chromatic aberration ~0.05, IOR ~1.4, thickness ~0.6). It slowly turns, floats, and tilts toward the cursor. The dots bounce like typing.
- **On load:**
  - the headline letters rise in with SplitText (stagger 0.04s)
  - the line and buttons fade up
  - the bubble scales in from 0.8
- **On scroll** (pinned for 120%):
  - cloud layers move at different speeds (parallax)
  - the headline scales to 0.85 and fades
  - the bubble drifts up and shrinks
  - the camera feels like it rises through the clouds, with the front cloud layer growing until it fills the screen white, as the transition into chapter 2

### 2. The problem: "2:07 a.m."
- **Shown:** the sky crossfades from day to `sky-night` as you scroll. A phone mock-up rises from the bottom showing a restaurant's WhatsApp, with customer messages stacking up, timestamped 11:48 pm, 1:12 am, 1:47 am, 2:07 am, all unanswered.
- **Copy, revealed line by line:** "Your customers order at 2 a.m. Nobody's awake to answer." Then: "By morning, they've ordered somewhere else."
- **On scroll** (pinned for 150%): messages enter one by one, tied to scroll progress. A small "unread" counter ticks up. Don't invent statistics; the counter only counts the messages on screen.

### 3. The answer: "Siyaf replies"
- **Shown:** the sky moves from night to `sky-dawn`. In the same phone, replies appear: the agent answers each message in Roman Urdu and English, with the product's trace lines (`↳ search_menu("family deal") → 4 items`).
- **Copy:** "Siyaf answers in seconds, from your real menu, in your customer's language."
- **On scroll** (pinned for 150%): each reply types in (the dots, then the text) as scroll progresses. The phone tilts slightly in 3D (`rotateY` from -8° to 0°).

### 4. Order to kitchen: a horizontal journey
- **Shown:** a horizontal scroll track, pinned while the page scrolls sideways. It has four panels:
  1. the confirmed order message
  2. an order card printing like a kitchen ticket (the dashboard's ticket style)
  3. the `kitchen.jpg` photo with the ticket landing on the pass
  4. the owner's dashboard: the order in the rail and the KPI number ticking up
- **Copy per panel:** "Order confirmed" → "Sent to your kitchen" → "Cooked" → "On your dashboard, live"
- **On scroll:** `xPercent` scrubbed across the track for about 300% of scroll. Each panel's elements animate as it enters the centre (`containerAnimation`).

### 5. You stay in control
- **Shown:** split screen. On the left, a chat where the customer asks for a refund. On the right, a "Needs you" alert, then the owner pressing **Take over**. The founder's portrait mark appears as the owner's avatar.
- **Copy:** "Refunds, complaints, anything tricky: Siyaf hands it to you, with a one-line summary. Take over any chat. Hand it back when you're done."
- **On scroll:** the two halves slide in from opposite sides. The "Needs you" chip pulses once. Motion springs on the Take over button when hovered.

### 6. Everything it does
- **Shown:** a bento grid of six cards:
  - answers from your menu
  - Roman Urdu and English
  - understands voice notes
  - remembers regulars
  - knows your hours and delivery areas
  - order confirmation with a button
  Two cards use the `food-*.jpg` photos.
- **On enter:** cards stagger up (0.08s). Each has a small hover tilt (Motion, max 6°) and a light sheen sweeping across.

### 7. Pricing
Three plans, exactly as in `PRICING.md`: **Basic Rs 2,999 · Standard Rs 5,999 · Pro Rs 11,999** a month, for 200 / 600 / 1,500 customer chats, with extra chats at Rs 3 each.
- Standard is highlighted.
- Add the line: "WhatsApp's own message fees are billed to you by Meta."
- **On enter:** the price numbers count up from 0 once.

### 8. Close: sunset
- **Shown:** the full-bleed `sky-sunset` photo. Large text "Let your WhatsApp take orders tonight." with the Start free trial button. The glass bubble returns, small, beside the button.
- **On scroll:** the sunset photo slowly zooms (scale 1.1 → 1) as the section enters.

### Footer
The logo mark, © year, links (Pricing, Privacy, Contact, Log in).

---

## Nav
- Fixed at the top and transparent over the hero.
- After 80px of scroll it becomes a frosted bar (`backdrop-blur`, white at 70%) using Motion's `useScroll`.
- Contents: logo mark + "Siyaf", How it works, Pricing, Log in, and **Start free trial** (solid).

## Performance and accessibility (required)
- **`prefers-reduced-motion`:** no pinning, no scrubbing, no parallax, and the 3D bubble is a static render. Every chapter shows its final state as a normal stacked section. Build this path first, then add motion on top of it.
- **Under 768px wide:** no horizontal track (chapter 4 stacks vertically), shorter pins (at most 100%), and the 3D bubble at a lower pixel ratio. Test on a mid-range Android phone size.
- **Animate only transforms and opacity.** No layout properties.
- **Targets:** Lighthouse performance 85 or better on mobile, LCP under 2.5s (the hero photo), CLS under 0.05.
- **Real text:** all copy is real text in the HTML, never baked into images. Headings in order (one `h1`). Every photo has meaningful `alt` text, or empty `alt` if it's decorative.
- **Visible focus** states on every link and button.
- **Clean up** all ScrollTriggers, Lenis and the WebGL renderer when the component unmounts.

## Copy rules
- **No invented numbers:** no customer counts, testimonials or review stars until they're real.
- **Product mock-ups** use the sample restaurant Daal & Dough and PKR prices, as in the dashboard mocks.
- **Plain English.** Short sentences.

## Build order (stop for review after each)
1. Routing, the libraries, the asset folder with `CREDITS.md`, the nav, and chapter 1 (hero with the photo and 3D bubble, including the reduced-motion version)
2. Chapters 2 and 3 (night to dawn, the phone conversation)
3. Chapter 4 (horizontal order journey)
4. Chapters 5–8 and the footer
5. Performance pass: Lighthouse on mobile, image sizes, mobile layout, reduced motion

After each part, run lint and typecheck, take desktop and mobile screenshots, commit, and stop.
