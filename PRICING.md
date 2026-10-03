# Pricing and Billing

Instructions for Claude Code. This file is the decision record for Siyaf's pricing (**locked**, don't change the numbers) and the spec for building billing. Read it fully before starting.

---

## 1. Locked plans

One subscription per restaurant (per tenant / WhatsApp number), billed in PKR.

| Plan key | Name | Price / month | AI chats included | Extra chats |
|---|---|---|---|---|
| `basic` | Basic | Rs 2,999 | 200 | Rs 3 each |
| `standard` | Standard | Rs 5,999 | 600 | Rs 3 each |
| `pro` | Pro | Rs 11,999 | 1,500 | Rs 3 each |

- **One "AI chat"** = one customer conversation the agent replied in during the month. This is already how `services/billing.py` counts usage: each conversation counts once per calendar month.
- **Yearly billing:** 10× the monthly price (2 months free). Rs 29,990 / Rs 59,990 / Rs 119,990.
- **Free trial:** 14 days, capped at 100 AI chats. No payment details needed to start.
- **Extra chats** are added to the next invoice. They are never charged mid-month.
- **WhatsApp fees are not included.** Meta bills each restaurant directly for replies after the first 1,000 free each month. Siyaf never pays or resells Meta fees.

**Requires the cheap AI model in production.** These prices assume roughly Rs 1.7 of AI per chat (Groq `openai/gpt-oss-120b`). Production must run `LLM_PROVIDER=groq`. On `gpt-4.1` a chat costs about Rs 17 and every plan loses money.

---

## 2. Payments

| | Choice | Why |
|---|---|---|
| **Provider** | **Safepay** (safepay.com.pk, API docs: apidocs.getsafepay.com) | Pakistani and regulated. Accepts cards, bank accounts and wallets. Has subscriptions, invoices and payment links through an API. |
| **Not used** | Stripe | Doesn't onboard Pakistani businesses. |
| **Not used** | Paddle / Lemon Squeezy | USD only, about 10% fees on a Rs 2,999 plan. Revisit only for customers outside Pakistan. |
| **Not used** | PayFast direct | Weak support for saved cards and recurring billing. |

**How restaurants pay:**

- **Card:** saved through Safepay checkout, then charged automatically each period.
- **Wallets (JazzCash, Easypaisa) and bank transfer:** can't be charged automatically. Each period an invoice is created and its **Safepay payment link** is sent to the owner on WhatsApp and email.

**Before integrating:** Safepay needs a registered business with a business bank account. Until the merchant account is approved, use **manual mode** (section 5).

---

## 3. Data model

Add to the tenant:

```python
class Subscription(BaseModel):
    plan: Literal["basic", "standard", "pro"] = "basic"
    interval: Literal["month", "year"] = "month"
    status: Literal["trialing", "active", "past_due", "paused", "canceled"] = "trialing"
    trial_ends_at: Optional[datetime]
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]
    payment_method: Optional[Literal["card", "payment_link", "manual"]] = None
    safepay_customer_id: Optional[str] = None
    safepay_subscription_id: Optional[str] = None
    cancel_at_period_end: bool = False
```

New collection `invoices`:

```python
class Invoice(BaseModel):
    invoice_id: str                     # "INV-2026-000123"
    tenant_id: str
    period_start: datetime
    period_end: datetime
    lines: List[InvoiceLine]            # plan fee, extra chats (count × Rs 3)
    amount_pkr: int                     # whole rupees
    status: Literal["open", "paid", "void"]
    due_at: datetime
    paid_at: Optional[datetime]
    method: Optional[Literal["card", "payment_link", "manual"]]
    safepay_tracker: Optional[str]      # Safepay's reference for this payment
    payment_url: Optional[str]          # payment link for wallets and bank transfer
```

In `services/billing.py`, replace the placeholder `PLANS` with the table in section 1: keys, prices and included chats. Map existing tenants with plan `starter` / `growth` / `scale` to `basic` / `standard` / `pro`.

---

## 4. Billing lifecycle

| When | What happens |
|---|---|
| Restaurant created | `status = trialing`, `trial_ends_at = now + 14 days`. The trial cap of 100 chats is enforced by the existing usage counter. |
| Trial ends or reaches 100 chats | The owner must choose a plan and payment method. Until then, the agent stops replying to customers, and the dashboard shows a blocking banner with a "Choose a plan" button. |
| Owner picks a plan | **Card:** Safepay checkout, card saved, first charge now, `status = active`. **Payment link:** invoice created, link shown, and `status = active` once the webhook confirms payment. |
| Each period end | Invoice created with the plan fee plus extra chats from the closing period. Cards are charged automatically. Payment links are sent on WhatsApp and email, due in 7 days. |
| Payment fails or isn't made | `status = past_due`. Reminders go out on days 0, 3 and 6 on WhatsApp and email. The agent keeps working. |
| 7 days past due | `status = paused`. The agent stops replying, and customers get the restaurant's fallback message. The owner can still sign in and pay, and paying reactivates immediately. |
| Plan change | Upgrades take effect immediately, with the price difference prorated on the next invoice. Downgrades take effect at the next period. |
| Cancel | `cancel_at_period_end = true`. Everything works until the period ends, then `status = canceled`. |

**Agent gate:** before `run_agent_turn` in the WhatsApp webhook, skip the agent when the subscription is `paused`, `canceled`, or a trial over its limits. The inbound message is still saved to the inbox, so the owner sees it.

---

## 5. Manual mode (build first)

This is for the first restaurants, before the Safepay account is approved:

- Invoices are created exactly as in section 4, with `method = manual`.
- The invoice shows Siyaf's bank account and Raast details for transfer, plus an invoice number to use as the reference.
- The **founder console** gets an Invoices page that lists open invoices with a "Mark as paid" button. It records `paid_at`, `method = manual`, and an optional note such as the transaction reference.
- Everything else (statuses, reminders, pausing) works the same, so switching to Safepay later only changes how invoices get paid.

---

## 6. Safepay integration (after approval)

- `POST /billing/checkout` with `{ plan, interval, method: "card" | "payment_link" }`:
  - For cards, create a Safepay subscription or saved-card session and return the hosted checkout URL.
  - For payment links, create the invoice and a Safepay payment link and return it.
- `POST /billing/webhooks/safepay`: **verify the signature first** and reject anything unsigned. Handle payment success (invoice → `paid`, subscription → `active`, period moves forward), payment failure (→ `past_due`), and subscription cancellation. Make it idempotent by keying on Safepay's event or tracker ID.
- Store Safepay keys in environment variables: `SAFEPAY_API_KEY`, `SAFEPAY_SECRET_KEY`, `SAFEPAY_WEBHOOK_SECRET`, `SAFEPAY_ENV=sandbox|production`. Add them to `render.yaml` with `sync: false`.
- Read Safepay's current API docs before writing the client. Don't guess endpoint names.

---

## 7. Screens

- **Dashboard → Billing** (`/dashboard/billing`):
  - current plan and status badge, AI chats used this month against the allowance (existing `/billing/usage`)
  - next invoice date and estimated amount
  - **"Your WhatsApp fee this month (paid to Meta): about Rs X"**, calculated as replies over 1,000 × Rs 4.2
  - Change plan, Update payment method, Cancel
  - an invoice table with Pay buttons on open invoices
- **Plan picker dialog:** three plan cards with a Monthly / Yearly toggle, then the payment method choice (Card, or "JazzCash, Easypaisa or bank transfer"). Use the same shadcn Dialog pattern as setup.
- **Banners:** trial days left, past due with a Pay now button, and paused with a Pay now button. These show on every dashboard page.
- **Founder console → Invoices:** all tenants' invoices with filters (open, past due, paid) and "Mark as paid" for manual mode.

---

## 8. Build order

Stop for review after each part.

1. **Plans and trial:** replace `PLANS`, add the subscription to the tenant, enforce the trial, gate the agent, and add the Billing page in read-only form.
2. **Manual invoicing:** the invoices collection, generating an invoice each period (a daily scheduled job), reminders, pausing, and Mark as paid in the founder console.
3. **Plan picker and plan changes:** upgrades, downgrades and cancel.
4. **Safepay:** checkout, payment links and webhooks, tested in sandbox.

Not included: taxes and GST on invoices (confirm with an accountant before invoicing at scale), refunds (do them manually through Safepay's dashboard for now), and international pricing.
