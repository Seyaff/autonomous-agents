# Pricing and Billing

Instructions for Claude Code. This file is the decision record for Siyaf's pricing (**locked**, don't change the numbers) and the spec for building billing. Read it fully before starting.

**There is no real payment provider yet.** Payments go through a **dummy provider** that always succeeds and shows "Payment done". Build everything behind a small provider interface, so a real gateway can replace the dummy later without touching plans, invoices or screens.

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
- **Free trial:** 14 days, capped at 100 AI chats. No payment needed to start.
- **Extra chats** are added to the next invoice. They are never charged mid-month.
- **WhatsApp fees are not included.** Meta bills each restaurant directly for replies after the first 1,000 free each month. Siyaf never pays or resells Meta fees.

**Requires the cheap AI model in production.** These prices assume roughly Rs 1.7 of AI per chat (Groq `openai/gpt-oss-120b`). Production must run `LLM_PROVIDER=groq`. On `gpt-4.1` a chat costs about Rs 17 and every plan loses money.

---

## 2. Payments: dummy provider

- Add `services/payments/` with a small interface:

  ```python
  class PaymentProvider(Protocol):
      name: str
      async def pay_invoice(self, invoice: Invoice, method: str) -> PaymentResult: ...
  ```

  `PaymentResult` has `ok: bool`, `reference: str` and an optional `error: str`.
- Add `DummyPaymentProvider`. `pay_invoice` waits about one second, then returns `ok=True` with `reference="DUMMY-<random>"`. Nothing is charged and no external service is called.
- Pick the provider with `PAYMENTS_PROVIDER=dummy`, the default and the only value for now. Add it to `render.yaml` and `.env.example`.
- **Label it honestly in the UI.** While the dummy provider is active, the payment dialog shows a small "Test payment, no money is charged" badge. Never claim a real charge happened.

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
    provider: Optional[str]             # "dummy" for now
    payment_reference: Optional[str]    # "DUMMY-…"
```

In `services/billing.py`, replace the placeholder `PLANS` with the table in section 1: keys, prices and included chats. Map existing tenants with plan `starter` / `growth` / `scale` to `basic` / `standard` / `pro`, and give existing tenants a 14-day trial starting now.

---

## 4. Billing lifecycle

| When | What happens |
|---|---|
| Restaurant created | `status = trialing`, `trial_ends_at = now + 14 days`. The trial cap of 100 chats is enforced by the existing usage counter. |
| Trial ends or reaches 100 chats | The owner must choose a plan and pay. Until then, the agent stops replying to customers, and the dashboard shows a blocking banner with a "Choose a plan" button. |
| Owner picks a plan and pays | An invoice is created for the first period. The dummy provider pays it, the invoice is marked `paid`, `status = active`, and the period starts now. |
| Each period end | A daily scheduled job creates the next invoice: plan fee plus extra chats from the closing period, `status = open`, due in 7 days. The owner pays it from the Billing page. |
| Invoice unpaid at period end | `status = past_due`. The agent keeps working, and the dashboard shows a Pay now banner. |
| 7 days past due | `status = paused`. The agent stops replying, and customers get the restaurant's fallback message. The owner can still sign in and pay, and paying reactivates immediately. |
| Plan change | Upgrades take effect immediately: a prorated invoice is created and paid in the same dialog. Downgrades take effect at the next period. |
| Cancel | `cancel_at_period_end = true`. Everything works until the period ends, then `status = canceled`. |

**Agent gate:** before `run_agent_turn` in the WhatsApp webhook, skip the agent when the subscription is `paused`, `canceled`, or a trial over its limits. The inbound message is still saved to the inbox, so the owner sees it.

---

## 5. API

```
GET  /billing/subscription            → { subscription, plan details, usage (existing /billing/usage data) }
GET  /billing/plans                   → the three plans with monthly and yearly prices
POST /billing/checkout                body: { plan, interval } → creates the invoice, pays it through the provider, returns { invoice, subscription }
POST /billing/invoices/{id}/pay       → pays an open invoice through the provider
POST /billing/cancel                  → sets cancel_at_period_end
GET  /billing/invoices                → the tenant's invoices, newest first
```

All require `require_owner`. A failed payment returns `402` with the provider's error, and the invoice stays `open`.

---

## 6. Screens

- **Dashboard → Billing** (`/dashboard/billing`):
  - current plan and status badge, AI chats used this month against the allowance
  - next invoice date and estimated amount
  - **"Your WhatsApp fee this month (paid to Meta): about Rs X"**, calculated as replies over 1,000 × Rs 4.2
  - Change plan and Cancel buttons
  - an invoice table with a Pay button on open invoices
- **Plan picker dialog:** three plan cards with a Monthly / Yearly toggle, the total for the selected plan, then **Pay Rs X**. Use the same shadcn Dialog pattern as setup.
- **Payment flow:** clicking Pay shows a spinner ("Processing payment…") for about a second, then a success state with a check icon: **"Payment done"**, the amount, the invoice number and "Your Standard plan is active until 3 Nov 2026". A Done button closes the dialog. The "Test payment, no money is charged" badge stays visible throughout.
- **Banners on every dashboard page:** trial days left (with "Choose a plan"), past due (with "Pay now"), paused (with "Pay now").

---

## 7. Build order

Stop for review after each part.

1. **Plans and trial:** replace `PLANS`, add the subscription to the tenant, migrate existing tenants, enforce the trial, gate the agent, and add the Billing page in read-only form.
2. **Dummy payments:** the provider interface, the dummy provider, invoices, checkout and pay endpoints, the plan picker, and the "Payment done" flow.
3. **Renewals and plan changes:** the daily invoice job, past due and pause rules, banners, upgrades, downgrades and cancel.

Not included: a real payment gateway, taxes on invoices, refunds, and international pricing.
