# Siyaf Design System

The design rules for the Siyaf dashboard.

Siyaf has two audiences, and each gets its own workspace:

| Audience | Workspace | Their job | What success looks like |
|---|---|---|---|
| **Restaurant owner** (the customer) | `/dashboard/*` | Let the agent handle WhatsApp queries and orders, and step in only when needed | More orders and fewer missed messages, for less staff time |
| **Founder** (you) | `/founder/*` | Run Siyaf itself on autopilot: find restaurants, pitch them, convert them, keep them paying | New paying tenants with minimal manual work, and no tenant left in trouble |

The two workspaces share the same tokens and components but have separate navigation. Founder pages appear only for the founder role.

Reference prototype: Siyaf Service Console (Claude artifact).

---

## 1. Principles

1. **Operational, not decorative.** Owners use this during service. Show what needs a person first and vanity numbers last.
2. **Color carries meaning.** The base is neutral. The four status colors below are the only hues on screen. Nothing gets color just for decoration.
3. **Show the agent's work.** Whenever the AI acts (searches the menu, creates an order, escalates), the UI shows it so the owner can trust it.
4. **A person can always take over.** Every AI-run surface has a visible switch for a person to take over and hand back.
5. **Paper for the kitchen.** Order tickets look like printed receipts. This is the one place the product uses a skeuomorphic look.
6. **Money uses each tenant's own currency.** Read `tenant.currency`. Never hardcode Rs or $.

---

## 2. Tokens

Replace the grayscale shadcn values in `src/app/globals.css`. shadcn components read these variables, so every component picks up the new look without changes.

### Color

| Token | Light | Dark | Use |
|---|---|---|---|
| `--background` | `#e9ecf1` | `#0d1117` | App background |
| `--card` | `#ffffff` | `#151a23` | Panes, popovers |
| `--muted` | `#f3f5f8` | `#10151d` | Inset areas (thread background, rail) |
| `--foreground` | `#131925` | `#e5e9f0` | Text, primary buttons |
| `--muted-foreground` | `#5b6475` | `#8d97a8` | Secondary text, labels |
| `--border` | `#dbe0e8` | `#252c39` | All borders |
| `--primary` | `#131925` | `#e5e9f0` | Primary actions (the ink color, not a brand hue) |

Status colors are the only accents. Each one has a `-soft` background variant.

| Token | Light | Dark | Meaning |
|---|---|---|---|
| `--ai` / `--ai-soft` | `#b87800` / `#fbf0d6` | `#f0b43c` / `#33270c` | The agent is acting, or the agent created this |
| `--need` / `--need-soft` | `#c8372a` / `#fbe5e1` | `#f0705f` / `#3a1c18` | Needs a person, late, failed |
| `--ok` / `--ok-soft` | `#1e7f4f` / `#dff2e7` | `#4cc488` / `#12301f` | Done, delivered, resolved |
| `--new` / `--new-soft` | `#2c58c9` / `#e2e9fb` | `#7d9ef5` / `#1a2545` | New, or the owner is acting ("You") |

These paper colors are the same in both themes:

| Token | Value | Use |
|---|---|---|
| `--paper` | `#fffdf6` | Ticket background |
| `--paper-ink` | `#1d1a14` | Ticket text |
| `--paper-muted` | `#6e675a` | Ticket secondary text |
| `--paper-line` | `#d9d2c2` | Ticket dashed rules |

Map `--destructive` to `--need`. Derive `--chart-1…5` from `--foreground` at decreasing opacity, and use status colors in charts only when a series is a status.

### Type

| Role | Font | Use |
|---|---|---|
| Display | Familjen Grotesk 600/700 | Page and pane titles, names in headers |
| Body | Hanken Grotesk 400/500/600 | Everything else |
| Mono | IBM Plex Mono 400/500/600 | Order IDs, money, times, counts, agent traces, tickets, uppercase labels |

Load the fonts with `next/font/google` in `src/app/layout.tsx`, replacing Geist.

Type scale (px): 11 · 12 · 13 · 14 (base) · 15 · 17 · 22 · 28.

- Uppercase labels: mono, 11px, `letter-spacing: .08em`.
- Every number uses `tabular-nums`.

### Shape and space

- Radius: panes 12px, buttons and inputs 8px, chips 5px, tickets 4px, chat bubbles 12px with a 4px "tail" corner.
- Spacing steps: 4 · 8 · 12 · 16 · 24. Space between panes is 12px.
- Shadows: tickets and toasts only. Panes use a border and no shadow.

---

## 3. Layout patterns

Every screen uses one of these seven patterns.

### A. Console (three panes)

```
┌ header: workspace · tabs · agent state · plan usage ───────────┐
│ KPI strip (inline numbers, not tiles)                          │
├────────────┬───────────────────────────┬───────────────────────┤
│ Queue      │ Live thread               │ Rail                  │
│ grouped by │ bubbles + agent trace     │ tickets by status     │
│ status     │ takeover bar + composer   │                       │
└────────────┴───────────────────────────┴───────────────────────┘
```
- Column widths: `300px | 1fr | 400px`. Under 1180px the rail moves below the other two. Under 760px everything stacks into one column.
- Group the queue in this order: **Needs you → Agent handling → Resolved today**.
- Each pane scrolls on its own. The page itself does not scroll.

### B. List and detail (two panes)

```
┌ list 320px ─────┬ detail ──────────────────────────────┐
│ filter/search   │ header: name · status chip · actions │
│ rows            │ body                                 │
└─────────────────┴──────────────────────────────────────┘
```
- The selected row gets a 3px ink bar on its left edge.
- On mobile the list and detail become separate routes.

### C. Ledger (dense table)

- Use TanStack Table, already installed.
- Filters sit above the table as chips, not in a sidebar.
- Status is shown as a chip. Money and IDs use the mono font and are right-aligned.
- Row height is 44px. Clicking a row opens the detail view (pattern B) or a sheet.

### D. Rail (status columns)

- Columns follow the backend order states (see §5). Each ticket has one forward action, for example `Send to kitchen →`.
- A ticket that is past its ETA gets a 4px red stripe on the left and a "Late by N min" chip.
- New tickets appear with a print animation, which is turned off when the user prefers reduced motion.

### E. Wizard

- A step list on the left (desktop) or on top (mobile), with one task per step.
- The primary action is always at the bottom right. Users can go back without losing what they entered.

### F. Settings form

- A single column, at most 640px wide, with grouped sections.
- Each section saves on its own and shows inline "Saved" confirmation.

### G. Reading

- A single column, at most 68 characters wide, for reports and legal pages.

---

## 4. Components

| Component | Spec |
|---|---|
| **Status chip** | Mono 11px, a dot plus a label, `-soft` background with full-color text. Only status values may use it. |
| **Agent trace line** | Mono 12px, right-aligned under the agent's bubble. Format: `↳ tool_name(args) → result · 0.18s`. The `↳` is `--ai`, the result is `--ok`, and an escalation is `--need`. |
| **Chat bubble** | Customer: card background, aligned left. Agent: `--ai-soft` background, aligned right, labeled "Agent". Owner: `--new-soft` background, aligned right, labeled "You". System events: a centered, dashed-border, mono line. |
| **Takeover bar** | In the thread header: a status chip plus a `Take over` / `Hand back to agent` button. The composer is disabled while the agent is in control, with the placeholder "The agent is replying. Take over to type." |
| **Quick replies** | Pill buttons above the composer, offered when the chat has been escalated (refund, compensation, call back). |
| **Ticket** | Paper colors, perforated top edge, mono 12.5px. Shows ID, age, customer · area, payment method, item lines, delivery fee, total, a source chip ("via AI agent"), and one action. |
| **KPI strip** | One inline row: uppercase label + mono value. A value flashes `--ok` when it increases. No large number cards. |
| **Plan usage meter** | Lives in the header: "Growth plan · 1,284 / 2,000 AI conversations" with a 5px ink-colored bar. Hide it until billing exists (see §7). |
| **Tenant switcher** | Business name · branch, with the branch count underneath. Calls `/auth/switch-tenant`. |
| **Toast** | Ink background, states what happened. Example: "ORD-7F3A moved to the kitchen. Ayesha got a WhatsApp update." |
| **Empty state** | A one-line mono note in a dashed box that says what will appear and how it gets there. |

---

## 5. Status vocabulary

Status chips use the backend values. Don't invent new ones in the frontend.

| Backend value | Label | Color | Where |
|---|---|---|---|
| `pending` | New | `--new` | Order |
| `accepted` | Accepted | `--new` | Order |
| `preparing` | In the kitchen | foreground | Order |
| `out_for_delivery` | On the way | foreground | Order |
| `delivered` | Delivered | `--ok` | Order |
| `cancelled` | Cancelled | `--need` | Order |
| takeover off (planned flag) | Agent replying | `--ai` | Conversation |
| takeover on (planned flag) | You're replying | `--new` | Conversation |
| message `sender: agent` / `human` | Agent / You | `--ai` / `--new` | Message |
| escalated (planned) | Needs you | `--need` | Conversation |
| conversation `closed` | Resolved | `--ok` | Conversation |
| message `failed` | Not sent | `--need` | Message |

`components/dashboard/data-table.tsx` currently uses `in_kitchen`, `ready` and `confirmed`, which the backend doesn't have. Switch it to the values above.

---

## 6. Page map

Status key: ✅ wired to the backend · 🟡 mock data · ⬜ missing

| Route | Pattern | Backend | Status | What it needs |
|---|---|---|---|---|
| `/login`, `/signup` | Auth (centered card) | `/auth/*`, `/auth/google` | ✅ | Apply the new tokens and fonts only. |
| `/onboarding` | E. Wizard | `/tenant/create`, `PATCH /tenant/current`, `/tenant/upload-menu-pdf`, `/tenant/meta-embedded-signup` | ✅ | Restyle the step list. Finish on a "Send a test message" step that shows the agent's first reply. |
| `/dashboard` | A. Console | `/inbox/conversations`, `/ws/inbox`, `/orders`, `/orders/stats/summary` | 🟡 | Replace the four stat cards and the dummy orders table with the console: queue, live thread, rail and KPI strip. This is the home screen. |
| `/dashboard/inbox`, `/inbox/[id]` | B. List and detail | `/inbox/conversations[/{id}]`, `/read`, `/messages`, `/ws/inbox` | 🟡 | Remove the email-style mock (Sent, Drafts, Trash, `mails`). Use the queue groups, bubbles, trace lines, takeover bar and quick replies. |
| `/dashboard/orders` | D. Rail + C. Ledger (toggle) | `GET /orders`, `PATCH /orders/{id}`, `/orders/stats/summary` | ⬜ | Rail for today, ledger for history, with status filters and a ticket detail sheet. |
| `/dashboard/menu` | C. Ledger + upload | `/knowledge` (list, `upload-pdf`, `add-text`, `DELETE`, `test-search`) | ⬜ | A document list plus a "Ask the agent" test box that shows the trace for each search. |
| `/dashboard/reports` | G. Reading + KPI strip | `/analytics/7day-summary`, `/analytics/weekly-reports`, `POST /analytics/weekly/generate` | ⬜ | Show the 7-day summary up top, with the weekly reports listed below as readable documents. |
| `/dashboard/settings` | F. Settings form | `/tenant/current`, `/tenant/meta-embedded-signup` | ⬜ | Sections for profile, delivery (fee, prep time), WhatsApp connection status, team, and plan & usage. |
| `/founder` | A. Console (founder version) | `/founder/campaigns`, `/founder/reply-handler` | ⬜ | The founder's home screen. Queue: prospects who replied, grouped Hot → Warm → Not interested. Thread: the reply, the agent's intent analysis and drafted answer, with takeover. Rail: the pipeline (see below). |
| `/founder/leads` | C. Ledger → B. detail | `POST /founder/lead-hunt`, `/founder/campaigns`, `/campaigns/{id}/export` | ⬜ | Campaign list, lead table with fit score and Warm/Hot/Premium tier, Excel export. Every lead shows its source; leads the LLM made up are never shown (see §7). |
| `/founder/outreach` | B. List and detail | `/founder/outreach/draft` | ⬜ | Pick a lead, edit the drafted email or WhatsApp pitch, approve it to send. Sending is not built yet. |
| `/founder/tenants` | C. Ledger → B. detail | needs a new endpoint | ⬜ | Every restaurant on Siyaf: WhatsApp connected?, last order, AI-handled %, failed messages, escalations, plan. Unhealthy tenants sort to the top. |
| `/founder/billing` | C. Ledger | needs a new endpoint | ⬜ | Plans, invoices, usage per tenant, MRR. Nothing exists in the backend yet. |
| `/` (agent chat) | Chat (B detail only) | `/agent/query` | ✅ | This is an internal test console. Move it to `/founder/agent` and make `/` a landing page or a redirect. |

### Founder pipeline (rail on `/founder`)

`Found → Contacted → Replied → Demo booked → Trial (tenant created) → Paying`

Each card is one restaurant. It moves forward automatically when the system sees the event (outreach sent, reply received, tenant created through `/tenant/create`, first payment). It moves manually only when you drag it.
| `/privacy` | G. Reading | — | ✅ | Apply tokens only. |

### Shared chrome

- **`components/sidebar/app-sidebar.tsx`:** remove the template data ("Acme Inc", "Evil Corp.", the favorites and workspaces lists).
  - Navigation becomes: Live service · Inbox · Orders · Menu knowledge · Reports · Settings.
  - Add a Founder group (Leads, Outreach, Agent) that only appears for the founder role.
  - Replace the team switcher with the tenant switcher.
- **`src/app/layout.tsx`:**
  - Re-enable `ThemeProvider` so dark mode works.
  - Change `metadata.description`, which still reads "Generated by create next app".
  - Swap Geist for the fonts in §2.
- **Header (inside the dashboard layout):** add the agent state ("Agent on · WhatsApp number"), the plan usage meter, and a live unread count from `/ws/inbox`.

---

## 7. Feature roadmap

These are ranked by the business outcome each audience needs. Each one names the screen it belongs on.

### Restaurant owner

| # | Feature | Outcome | Screen | Backend |
|---|---|---|---|---|
| 1 | **Takeover and escalation.** Owner pauses the agent per chat; the agent hands refunds and complaints to the owner. | No double replies, and angry customers reach a person | Console, Inbox | Takeover flag the agent checks, `escalate` tool |
| 2 | **Item availability.** Mark items sold out for today. | Fewer wrong orders and cancellations | Menu knowledge | Availability list injected into the agent prompt |
| 3 | **Hours, closed mode, delivery zones** | Takes pre-orders when closed, rejects out-of-area orders | Settings | Tenant fields + prompt |
| 4 | **ROI report.** Orders and revenue taken by the agent, after-hours orders, staff hours saved. | Owner sees why Siyaf is worth paying for | Reports, KPI strip | Aggregate over `orders` |
| 5 | **Order status updates to customers.** Each ticket move sends a WhatsApp message. | Fewer "where is my order?" chats | Rail | Hook on `PATCH /orders/{id}` |
| 6 | **Owner alerts on WhatsApp.** Escalations, late orders, daily summary. | Owner doesn't need the dashboard open | Settings (alert preferences) | Email alerts exist; add WhatsApp |
| 7 | **Upsell in the agent** | Higher average order value | Reports (acceptance rate) | Prompt + order data |
| 8 | **Abandoned-chat follow-up and reorder campaigns** | Recovered and repeat orders | Campaigns (new page, C. Ledger) | Meta-approved templates and customer opt-in are required |

### Founder

| # | Feature | Outcome | Screen | Backend |
|---|---|---|---|---|
| 1 | **No invented leads.** `lead_generator.py` asks the LLM to make up businesses with phones and emails when search fails. Fail and show an error instead. | You never pitch fake or wrong numbers, which protects your WhatsApp number | Leads | Remove the LLM fallback |
| 2 | **Persistent leads.** Store each lead as its own record with a pipeline stage. Generate the Excel file on download. | The pipeline survives redeploys; files written to disk on Render are lost | Leads, `/founder` rail | `leads` collection |
| 3 | **Send outreach**, not only draft it. Approval step first, then automatic. | Outreach runs without you | Outreach | Email send exists (Gmail); WhatsApp needs templates |
| 4 | **Automatic reply intake.** Prospect replies arrive by themselves instead of through a manual `POST /reply-handler`. | Hot replies reach you within minutes | `/founder` console | Route replies to the founder number into the reply handler |
| 5 | **Lead → trial in one link.** The pitch includes a signup link that pre-fills onboarding. | Shorter path from "interested" to live | Onboarding | Signup token tied to the lead |
| 6 | **Scheduled autopilot.** Lead hunts, follow-ups and weekly owner reports run on a schedule. | The business runs while you sleep | `/founder` settings | No scheduler exists yet |
| 7 | **Tenant health** | You catch a broken WhatsApp connection or a failing agent before the owner churns | Tenants | New aggregate endpoint |
| 8 | **Billing and usage metering** | You get paid; plans limit AI conversations | Billing, plan meter | Nothing exists yet |

Build order: founder 1–2 (cheap, they prevent damage), then owner 1–3, then founder 3–4 and 6, then owner 4–5, then billing before the first paying customer.
