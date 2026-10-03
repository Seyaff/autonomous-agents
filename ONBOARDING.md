# Task: Rebuild restaurant onboarding as setup dialogs over the dashboard

Instructions for Claude Code. Read the whole file before starting.

Reference prototype (look and behavior): [Siyaf Setup Dialogs](https://claude.ai/artifact/2LQtJWXVvpGvxFE6Zj4oaq).

## What we're building

The current `/onboarding` page is deleted. New owners do setup in a sequence of shadcn Dialogs that open **on top of the dashboard**. The dashboard layout (sidebar and top bar) and a skeleton dashboard are always visible behind a blurred overlay.

Rules that must hold:

1. **Clean URLs.** Each step has its own path, such as `/setup/menu`. No query strings.
2. **Always on top of the dashboard.** The setup routes live inside the `(dashboard)` route group, so the sidebar, top bar and a dashboard backdrop always render behind the dialog.
3. **Can't be dismissed until finished.** Until the owner finishes the last step, there is no close button. Clicking outside, pressing Escape, using the browser back button or typing another dashboard URL never leaves setup. Any owner route sends them back to their current step.
4. **Resumable.** Progress is saved on the server after every step. Refreshing, logging out, or switching devices returns the owner to the same step.

## Before you write code

1. Read `frontend/AGENTS.md`. This repo uses Next.js 16, so check `node_modules/next/dist/docs/` before using routing APIs.
2. `src/components/ui/dialog.tsx` is the **Base UI** variant of shadcn (look for `data-open:` classes), not Radix. Use Base UI's API for controlled open state and dismissal. Don't assume Radix props like `onInteractOutside`.
3. Use the existing shadcn components in `src/components/ui/`: `dialog`, `button`, `input`, `field`, `label`, `select`, `checkbox`, `switch`, `tabs`, `badge`, `progress`, `alert`, `table`, `textarea`, `skeleton`, `card`. Don't add new UI libraries.
4. Use the existing theme tokens. No raw colors.

---

## Steps and URLs

| Order | URL | Dialog title | Required | Dialog width |
|---|---|---|---|---|
| 0 | `/setup/welcome` | Welcome to Siyaf | — | `sm:max-w-lg` |
| 1 | `/setup/restaurant` | Restaurant details | yes | `sm:max-w-lg` |
| 2 | `/setup/menu` | Upload your menu | no ("Skip for now") | `sm:max-w-lg`, `sm:max-w-xl` once items show |
| 3 | `/setup/hours` | Hours and delivery | yes | `sm:max-w-xl` |
| 4 | `/setup/agent` | Set up your agent | yes | `sm:max-w-xl` |
| 5 | `/setup/test` | Test your agent | yes (Continue is always enabled) | `sm:max-w-3xl` |
| 6 | `/setup/whatsapp` | Connect WhatsApp | no ("Do this later") | `sm:max-w-lg` |
| 7 | `/setup/done` | You're live / You're almost set | — | `sm:max-w-lg` |

- `/setup` (no step) redirects to the owner's current step.
- An unknown step slug returns `notFound()`.
- Steps 1–6 show "Step N of 6" and a `Progress` bar in the dialog header. Welcome and done don't.
- Step slugs and order live in one constant, `src/lib/setup.ts`, which is used everywhere. The backend has the same list (see below).

---

## Part A: Backend (`app/`)

Do this first. The frontend depends on it.

### A1. Setup progress on the tenant

Add to the tenant document and to `TenantPublic`:

```python
SETUP_STEPS = ["restaurant", "menu", "hours", "agent", "test", "whatsapp"]
SKIPPABLE = {"menu", "whatsapp"}

class SetupState(BaseModel):
    completed_steps: List[str] = []
    skipped_steps: List[str] = []
    completed_at: Optional[datetime] = None   # set when the owner finishes /setup/done
```

Also return a computed `setup.current_step` in `TenantPublic`: the first step in `SETUP_STEPS` that is neither completed nor skipped, or `"done"` when all are handled.

New endpoints, all requiring `require_owner`:

```
POST /tenant/current/setup/{step}   body: { "action": "complete" | "skip" }
     → 400 if step is unknown, 400 if "skip" on a required step,
       409 if an earlier required step isn't complete. Returns the SetupState.
POST /tenant/current/setup/finish
     → sets completed_at and sets user.is_onboarded = true. Returns the SetupState.
```

### A2. Creating the restaurant (step 1)

- Add `country` (ISO code: `PK`, `AE`, `SA`, `GB`, `US`), `city`, and `order_types: List[Literal["delivery", "takeaway", "dine_in"]]` to `CreateTenantRequest`.
- **Derive `currency` and `timezone` on the server from `country`.** Keep a small map in the backend and don't trust values from the client.
- `POST /tenant/create` sets `setup.completed_steps = ["restaurant"]`.
- **Stop setting `is_onboarded = true` when the tenant is created** (`api/v1/endpoints/tenant.py` around line 126). Only `/setup/finish` sets it.

### A3. Hours and delivery (step 3)

Extend `TenantUpdatePayload` (`PATCH /tenant/current`) with:

```python
operating_hours: Optional[List[DayHours]]       # 7 entries: { day: "mon".."sun", open: "12:00", close: "23:30", closed: bool }
flat_delivery_fee: Optional[float]               # already exists
min_order_amount: Optional[float]
avg_prep_time_minutes: Optional[int]             # already exists
delivery_areas: Optional[List[str]]
payment_methods: Optional[List[Literal["cash_on_delivery", "card_on_delivery", "bank_transfer"]]]
order_types: Optional[List[Literal["delivery", "takeaway", "dine_in"]]]
```

A closing time earlier than the opening time means the day closes after midnight. Pass hours, delivery areas, minimum order and payment methods into `agents/customer_support/prompt.py`, so the agent refuses orders while closed or outside delivery areas.

### A4. Agent settings (step 4)

```python
class AgentSettings(BaseModel):
    language: Literal["match", "en", "roman_urdu"] = "match"
    tone: Literal["warm", "professional", "short"] = "warm"
    greeting: Optional[str] = None                 # None = generated from name and language
    escalate_on: EscalateRules = EscalateRules()   # refund: bool, complaint: bool, human_requested: bool, large_order_over: Optional[float]

PATCH /tenant/current/agent-settings   body: AgentSettings → AgentSettings
```

Store it as `tenant.agent_settings` and return it in `TenantPublic`. Use it in `compile_customer_support_prompt`: the reply language, tone and greeting, and exactly which situations must call the existing `escalate_to_owner` tool.

### A5. Menu items (step 2)

The menu is uploaded with the existing `POST /tenant/upload-menu-pdf`, which indexes it in Pinecone. Today nothing returns a structured list of items, so add:

- After a successful upload, run one LLM extraction over the parsed text that returns `[{name, category, price, description}]`. Save the items to a new `menu_items` collection with `tenant_id` and `doc_id`. Replace the tenant's previous items when a new menu is uploaded.
- Add `items_found` (a count) to the upload response.
- Add `GET /tenant/current/menu-items` → `{ items: MenuItem[], source_filename }`.
- Accept images (`image/jpeg`, `image/png`) as well as PDFs if the ingestion code can handle them. If it can't, accept PDF only and say so in the dropzone text.

### A6. Test chat (step 5, and "Check what your agent knows" in step 2)

```
POST   /agent/test            body: { message: str }
       → { reply: str, trace: [{ tool, args, result_summary }], escalated: bool }
DELETE /agent/test            → clears the owner's test conversation
```

- Run the real customer support agent (`run_customer_support_turn`) with a new `test_mode=True` parameter, using thread ID `test:{tenant_id}:{user_id}`.
- In test mode, nothing has side effects:
  - `create_order_tool` returns a `TEST-XXXX` ID without inserting an order, updating the customer profile or broadcasting.
  - `escalate_to_owner` returns its normal text but doesn't touch any conversation.
  - Nothing is saved to the inbox, nothing is sent on WhatsApp, and no customer memory or facts are written.
- Build `trace` from the agent's result: each AI tool call paired with its tool message. Shorten `result_summary` to 120 characters.
- Mark the test chat as test traffic so it doesn't count toward usage.

### A7. Redirect target

In `api/v1/endpoints/auth.py`, the Google callback's default `next` is `/onboarding`. Change it to `/setup`.

**Stop after Part A for my review.** Show the new endpoints and a test-mode chat working.

---

## Part B: Routing and the "can't leave" gate (`frontend/`)

### B1. Files

```
src/lib/setup.ts                                   STEPS constant, step types, helpers (stepIndex, isRequired, nextStep)
src/app/(dashboard)/setup/layout.tsx               renders <SetupBackdrop /> + the persistent <SetupDialog> shell
src/app/(dashboard)/setup/page.tsx                 redirects to /setup/{currentStep}
src/app/(dashboard)/setup/[step]/page.tsx          validates the slug, renders that step's content inside the shell
src/components/setup/setup-dialog.tsx              Dialog shell: header (step label + progress), body slot, dismissal rules
src/components/setup/setup-backdrop.tsx            skeleton dashboard home (Skeleton components only, no data queries)
src/components/setup/steps/*.tsx                   welcome, restaurant, menu, hours, agent, test, whatsapp, done
src/hooks/setup/use-setup-state.ts                 current step, completed/skipped steps, isComplete
src/hooks/setup/use-setup-step.ts                  mutation: POST /tenant/current/setup/{step}
src/hooks/setup/use-test-chat.ts                   POST/DELETE /agent/test
src/hooks/setup/use-menu-items.ts                  GET /tenant/current/menu-items
src/services/setup/setup.service.ts                the API calls
```

The **Dialog shell lives in `setup/layout.tsx`**, so it stays mounted while the URL changes between steps. The overlay doesn't flash. Only the content inside swaps, with a short fade and zoom keyed on the step.

### B2. Blur behind the dialog

Add an `overlayClassName` prop to `DialogContent` in `src/components/ui/dialog.tsx` and pass it to `DialogOverlay`. Setup uses `overlayClassName="bg-black/40 backdrop-blur-sm"`. Other dialogs in the app keep their current overlay.

### B3. Dismissal rules

While `setup.completed_at` is null:

- `DialogContent showCloseButton={false}`.
- The dialog is controlled with `open` always `true`. Ignore close requests in `onOpenChange`, and turn off outside-click dismissal with Base UI's option for it. Escape must not close it either.
- The sidebar and top bar render behind the overlay but can't be clicked, because the modal overlay covers them.

After setup is completed, `/setup/menu` and `/setup/whatsapp` stay reachable for skipped steps (see B5). In that case the dialog **is** dismissible (close button, Escape, outside click), and closing returns to `/dashboard`.

### B4. The gate

Replace the `is_onboarded` redirect logic in `src/components/providers/auth-provider.tsx`:

| Situation | Redirect |
|---|---|
| Owner with no `active_tenant_id` | Allow only `/setup/welcome` and `/setup/restaurant`. Everything else → `/setup/welcome` |
| Owner with a tenant and `setup.completed_at == null`, outside `/setup/*` | `/setup/{current_step}` |
| Owner on a step **after** their current step | `/setup/{current_step}`. Going back to earlier steps is allowed |
| Owner with setup complete, on `/setup/*` | `/dashboard`, except `/setup/menu` or `/setup/whatsapp` when that step was skipped |
| Founder | Unchanged (`/founder`) |

Also change every default of `"/onboarding"` to `"/setup"`:
- `src/components/login-form.tsx`
- `src/components/signup-form.tsx`
- `src/hooks/auth/use-google.ts`
- `src/app/(auth)/login/page.tsx`
- `src/components/MetaEmbeddedSignup.tsx`

### B5. Queries without a tenant

Before step 1 creates the tenant, every owner endpoint returns an error. While on `/setup/*`:

- Data hooks used by the layout (current tenant, tenant switcher, unread count, inbox socket) need `enabled: !!activeTenantId`.
- `SetupBackdrop` renders skeletons only. It never fetches data.
- The sidebar shows the restaurant name once it exists. Before that it shows a skeleton.

### B6. Skipped steps after completion

On `/dashboard`, when `menu` or `whatsapp` is in `skipped_steps`, show a `Card` titled "Finish setting up". It lists each skipped step with a button linking to `/setup/menu` or `/setup/whatsapp`, and the sidebar Home item shows a badge with the remaining count. Completing a step removes it from `skipped_steps`.

**Stop after Part B for my review.** At this point the dialog shell, gate and URLs should work with placeholder step content.

---

## Part C: The dialogs

Every step dialog has a header (step label and progress for steps 1–6, a `DialogTitle` and a `DialogDescription`), a body, and a `DialogFooter` with **Back** (outline, hidden on welcome and restaurant) and the primary action on the right.

The primary action saves the step's data, calls `POST /tenant/current/setup/{step}` with `complete`, and goes to the next step's URL with `router.push`. While saving, the button shows a spinner and is disabled. A failed save shows the error inside the dialog in an `Alert` and stays on the step.

### Welcome: `/setup/welcome`
- A logo mark, the title "Welcome to Siyaf", and the description: "Let's get your WhatsApp ordering agent ready. Six short steps, about 10 minutes. Your progress is saved after every step."
- A "You'll need" list: your menu as a PDF or photo, your opening hours and delivery areas, and a Facebook account plus a phone number for WhatsApp.
- One button: **Get started** → `/setup/restaurant`. There's no "explore first", because setup can't be skipped.

### Restaurant: `/setup/restaurant`
- **Fields:** restaurant name (required), country (`Select`), city.
- Under them, a read-only line: `Currency [PKR] · Timezone [Asia/Karachi]` as `Badge`s, updated when the country changes. It's for display only, since the server derives both.
- **Order types:** three checkbox cards (Delivery, Takeaway, Dine-in). At least one is required.
- **Primary:** Continue → `POST /tenant/create`. If the tenant already exists (the owner came back), use `PATCH /tenant/current` instead. Then refetch `/auth/me` so `active_tenant_id` is set.

### Menu: `/setup/menu`
- **Empty state:** a dropzone with an upload icon, "Upload your menu", "PDF, JPG or PNG up to 20 MB. Photos of a printed menu work.", and a Choose file button. Dragging a file onto it also works.
- **Uploading:** a spinner, the file name, a `Progress` bar, and "Finding dishes, categories and prices."
- **Done:**
  - "N items found · filename" with a Replace button.
  - A `Table` (Item, Category, Price) in a scroll area about 200px tall. Prices are formatted with the tenant currency through `src/lib/currency.ts`.
  - "Check what your agent knows": an input and an Ask button that call `POST /agent/test`, showing the first trace line in mono plus the reply.
- **Footer:** "Skip for now" (ghost, calls `skip`) and Continue. Continue is disabled until items exist.

### Hours: `/setup/hours`
- `Tabs`: **Opening hours** and **Delivery & payment**.
- **Opening hours:** seven rows of `Switch` (open), day name, and opening and closing time inputs (disabled when the day is closed). Defaults: 12:00–23:30. Note underneath: "Closing after midnight counts toward the same day."
- **Delivery & payment:**
  - delivery fee and minimum order (number inputs with the currency as a hint)
  - usual delivery time (`Select`: 20, 30, 35, 45, 60 or 90 minutes)
  - delivery areas as a tag input: `Badge`s with a remove button, Enter adds an area, Backspace on an empty input removes the last one
  - payment methods as three checkbox cards
  - At least one payment method and, when delivery is on, one delivery area are required. Show the error on the tab that has it.
- **Primary:** Continue → `PATCH /tenant/current`.

### Agent: `/setup/agent`
- Reply language (`Select`: Match the customer, English, Roman Urdu) and tone (`Select`: Warm, Professional, Short and quick), side by side.
- **Greeting** (`Textarea`): pre-filled with a suggestion built from the restaurant name and language. Once the owner edits it, show "Reset to suggested".
- **"Always send to me":** rows with `Switch`es for refund requests, complaints, customer asks for a person, and orders over an amount (with an inline number input when on). Defaults: the first three on, large orders off.
- **Primary:** Continue → `PATCH /tenant/current/agent-settings`.

### Test: `/setup/test`
- **Two columns** (stacked on mobile):
  - **Left, a chat panel:** a header with the restaurant initial, name and "Test mode" `Badge`; the messages; and an input with a send button. Customer messages sit on the right in primary color, agent messages on the left in muted color. Each trace step appears as a small mono line with a wrench icon above the agent reply. When `escalated` is true, show a destructive `Badge`: "Sent to you under Needs you".
  - **Right, "Try these · n/6":** six buttons that send a sample message and get a check mark once tried: Say hello, Ask about the menu, Opening hours, Delivery, Test order, Complaint.
- The chat starts with the agent's greeting. A **Reset chat** ghost button calls `DELETE /agent/test`.
- **Primary:** Continue (always enabled).

### WhatsApp: `/setup/whatsapp`
- **Before connecting:**
  - an `Alert`: "The phone number must not be active in the WhatsApp or WhatsApp Business app. You can move an existing number, but its chat history won't come along."
  - a list of what you need: a Facebook account, a number that can receive an SMS or call, and your business name plus a website or Facebook page
- **Primary:** "Continue with Facebook" starts the existing `MetaEmbeddedSignup` flow → `POST /tenant/meta-embedded-signup`.
- **While connecting:** a list of steps with spinners and check marks.
- **On success:** an `Alert` saying "Connected to {display number}", then mark the step complete. The primary button becomes Continue.
- **"Do this later"** (ghost, left side of the footer) calls `skip`.

### Done: `/setup/done`
- **If WhatsApp is connected:** "You're live". Description: "Your agent now answers customers on WhatsApp. Conversations and orders appear in your dashboard."
- **If anything was skipped:** "You're almost set". List the skipped steps and say they stay on the dashboard checklist, and that the agent stays in test mode until WhatsApp is connected.
- **Primary:** "Go to dashboard" → `POST /tenant/current/setup/finish`, refetch the tenant and `/auth/me`, then `router.replace("/dashboard")`. The dialog closes with its normal exit animation.

---

## Part D: Clean-up

- Delete `src/app/onboarding/` and any components only it used.
- Search for `"/onboarding"` across `frontend/` and `app/`. There should be no references left.
- Run lint, typecheck and the backend tests. Then walk the whole flow in the browser with a new account:
  - sign up and finish every step
  - refresh in the middle of a step
  - try `/dashboard/orders` before finishing
  - skip the menu and WhatsApp steps, then finish them from the dashboard card

## Out of scope

The landing page, team invites, and billing or plan selection. The `/` route keeps its current behavior.
