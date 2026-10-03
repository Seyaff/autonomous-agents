# Dynamic Data Plan: Restaurant Dashboard

How to replace the mock data in the owner dashboard (`/dashboard/*`) with real data. Based on `main` at `bc19cba`, after the redesign merge.

It covers the API that exists today, what the dashboard needs that the backend doesn't have, the data model changes, the new endpoints, and the build order. The founder side is out of scope.

---

## 1. Feature-by-feature status

✅ works with the real API today · 🟡 an API exists but is missing fields or behavior · ❌ no backend at all

| Dashboard feature | Frontend hook | Backend today | Status | Gap |
|---|---|---|---|---|
| Conversation list | `use-queue` → `GET /inbox/conversations` | Returns `ConversationListItem`, whose fields match the frontend `Conversation` type exactly | 🟡 | No `handled_by` or `escalation` field, so "Needs you" is guessed from `unread_count > 0` |
| Thread messages | `use-thread` → `GET /inbox/conversations/{id}` | Returns messages with an optional `agent_metadata` | 🟡 | The WhatsApp path never writes `agent_metadata`, and nothing records tool arguments, results or timings |
| Owner reply | `POST /inbox/conversations/{id}/messages` | Saves the message and sends it to WhatsApp | 🟡 | The agent keeps replying to the same customer |
| Mark read | `POST /inbox/conversations/{id}/read` | Works | ✅ | — |
| Live updates | `use-inbox-socket` → `/ws/inbox` | Emits `message.*`, `unread.count`, `order.*` | 🟡 | `agent.step` and `agent.reply` are declared in `schemas/ws_events.py` but never emitted. No typing or takeover events |
| Take over / Hand back | `use-thread.toggleTakeover` | Nothing | ❌ | Needs a flag on the conversation, endpoints, and an agent check |
| "Needs you" escalation | `use-queue` grouping | Nothing | ❌ | Needs an escalation tool and fields |
| Agent trace lines | `MockMessage.trace` | `AgentMeta.tools_called` exists but holds names only, and is never filled | ❌ | Needs a trace capture with arguments, result and duration |
| Typing indicator | `isAgentTyping` | Nothing | ❌ | Needs a WebSocket event |
| Read ticks | `message-ticks` via `message.status` | Status webhook exists | 🟡 | Outbound messages store `wamid: "pending"`, so Meta's delivered and read callbacks can't be matched. `send_whatsapp_message` returns `True` and drops the real wamid |
| Kitchen rail | `use-rail` → `GET /orders` | Works | 🟡 | No date filter for today's orders. No `delivery_fee`, `eta_minutes`, `source` or `conversation_id` fields |
| Move a ticket | `PATCH /orders/{id}` | Updates status and broadcasts | 🟡 | Any status can jump to any other (`delivered → pending` is allowed). The customer is never notified. No status history |
| KPI strip | `use-kpis` → `/orders/stats/summary` + `/analytics/7day-summary` | Works | 🟡 | The summary covers all time, not today. "Handled by AI %" and "median first reply" don't exist. Revenue includes pending orders |
| Tenant switcher | `tenant-switcher` | `/auth/me` returns tenant IDs only | 🟡 | No endpoint lists the user's tenants with names. No branch concept |
| Agent state indicator | `agent-state-indicator` | `GET /tenant/current` | 🟡 | The tenant has no `whatsapp_connected` or `agent_enabled` field. The frontend type expects them |
| Plan usage meter | `plan-usage-meter` | Nothing | ❌ | Needs billing and usage counting |
| Menu, Reports, Settings pages | "Coming soon" | `/knowledge/*`, `/analytics/*`, `PATCH /tenant/current` all exist | 🟡 | Frontend only. The backend is ready |

### Fix these first (found during the review)

1. **Security: `GET /tenant/current` returns the raw tenant document, including `whatsapp_access_token`.** Every logged-in owner's browser receives the WhatsApp token. Return a response model with an allow-list of fields.
2. When `tenant_id` can't be matched, the webhook falls back to `find_one({})` and answers as a random restaurant (`api/v1/endpoints/whatsapp.py`).
3. Inbound messages are saved with `customer_name = tenant.business_name`. Use the WhatsApp profile name from the webhook's `contacts[0].profile.name` instead.
4. `create_order_tool` hardcodes `$` in its confirmation text. Use `tenant.currency`.
5. `/orders/stats/summary` counts `pending` orders as revenue.

---

## 2. Data model changes (MongoDB)

All new fields are optional with defaults, so existing documents keep working without a migration.

### `conversations`

```python
class Escalation(BaseModel):
    active: bool = True
    reason: Literal["refund", "complaint", "human_requested", "agent_failed", "other"]
    summary: str                       # one line, written by the agent: "Wants refund for cold biryani, ORD-6A21"
    raised_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None  # user_id

class Conversation(BaseModel):          # existing fields unchanged
    ...
    handled_by: Literal["agent", "owner"] = "agent"
    handled_by_user_id: Optional[str] = None
    handed_over_at: Optional[datetime] = None
    escalation: Optional[Escalation] = None
    first_response_ms: Optional[int] = None  # time to the first agent reply, for the KPI
```

The queue group is computed on the server and returned as a field, so the frontend never guesses it:

| `group` | Rule |
|---|---|
| `needs_you` | `escalation.active == True` |
| `owner_handling` | `handled_by == "owner"` and not escalated |
| `agent_handling` | `status == "open"` and `handled_by == "agent"` |
| `resolved` | `status in ("closed", "archived")` |

Index: `{tenant_id: 1, "escalation.active": 1, last_activity_at: -1}`.

### `messages`: `agent_metadata`

```python
class TraceStep(BaseModel):
    tool: str                          # "search_menu", "create_order", "escalate"
    args: Dict[str, Any]               # redact phone numbers and addresses before saving
    result_summary: str                # at most 200 chars: "4 matches", "ORD-7F3A"
    status: Literal["ok", "error", "escalated"]
    duration_ms: int

class AgentMeta(BaseModel):            # extends the existing model
    agent_type: Literal["ai", "human"] = "ai"
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    latency_ms: Optional[int] = None
    tools_called: List[str] = []       # keep for compatibility
    trace: List[TraceStep] = []
```

`wamid` must hold the real ID from the Graph API response (`messages[0].id`), not `"pending"`.

### `orders`

```python
class StatusChange(BaseModel):
    status: OrderStatus
    at: datetime
    by: Literal["agent", "owner", "system"]
    by_user_id: Optional[str] = None
    customer_notified: bool = False

class Order(BaseModel):                 # existing fields unchanged
    ...
    conversation_id: Optional[str] = None
    source: Literal["ai_agent", "owner", "manual"] = "ai_agent"
    currency: str                       # copied from the tenant when the order is created
    subtotal: float
    delivery_fee: float                 # from tenant.delivery_settings.flat_delivery_fee
    total_amount: float                 # subtotal + delivery_fee, computed on the server, not trusted from the LLM
    eta_minutes: int                    # from tenant.delivery_settings.avg_prep_time_minutes
    status_history: List[StatusChange] = []
```

Allowed status changes (anything else returns `409`):

```
pending → accepted | cancelled
accepted → preparing | cancelled
preparing → out_for_delivery | cancelled
out_for_delivery → delivered
```

Index: `{tenant_id: 1, created_at: -1}` (needed for today's orders).

### `tenants`

```python
class Tenant(BaseModel):                # existing fields unchanged
    ...
    branch_name: Optional[str] = None   # "Gulberg III"
    brand_id: Optional[str] = None      # groups branches of one business
    agent_enabled: bool = True          # global pause switch for the agent
    whatsapp_status: Literal["connected", "disconnected", "error"] = "disconnected"
    whatsapp_last_error: Optional[str] = None
    whatsapp_checked_at: Optional[datetime] = None
```

Set `whatsapp_status` when Meta signup succeeds. Set it to `error` when a send fails with an auth error.

### New: `usage_counters` (for the plan meter, later)

```python
class UsageCounter(BaseModel):
    tenant_id: str
    period: str                         # "2026-10"
    ai_conversations: int = 0           # distinct conversations the agent replied in
    ai_messages: int = 0
    tokens_used: int = 0
    plan_limit_conversations: int       # copied from the plan
```

Unique index: `{tenant_id: 1, period: 1}`. Increment with `$inc` after each agent reply.

---

## 3. API changes

### Changed endpoints

| Endpoint | Change |
|---|---|
| `GET /inbox/conversations` | Add `group`, `handled_by`, `escalation` to each item. Add a `group` filter. Add `group_counts: {needs_you, owner_handling, agent_handling, resolved}` to the response |
| `GET /inbox/conversations/{id}` | Same new fields. Messages include `agent_metadata.trace` |
| `POST /inbox/conversations/{id}/messages` | If `handled_by == "agent"`, switch it to `"owner"` automatically, because sending a reply means taking over |
| `GET /orders` | Add `from` and `to` (ISO datetimes, interpreted in the tenant's timezone) |
| `PATCH /orders/{id}` | Validate status changes, append to `status_history`, send the customer a WhatsApp update, and return `customer_notified: bool` |
| `GET /tenant/current` | Use a response model with no tokens. Add `whatsapp_status`, `agent_enabled`, `branch_name` |

### New endpoints

```
POST  /inbox/conversations/{id}/takeover              → { conversation }   handled_by = owner
POST  /inbox/conversations/{id}/handback              → { conversation }   handled_by = agent, resolves any escalation
POST  /inbox/conversations/{id}/escalation/resolve    → { conversation }
GET   /dashboard/kpis?range=today|7d                  → KpiResponse
GET   /tenant/mine                                    → TenantSummary[]   (for the switcher)
PATCH /tenant/current/agent  { enabled: bool }        → { agent_enabled }
GET   /billing/usage                                  → UsageResponse     (later)
```

```python
class KpiResponse(BaseModel):
    range: Literal["today", "7d"]
    currency: str
    orders: int
    revenue: float                      # delivered + in-progress, excluding pending and cancelled
    conversations: int
    ai_handled_pct: float               # conversations with no takeover / all conversations
    median_first_reply_s: Optional[float]
    needs_you: int

class TenantSummary(BaseModel):
    tenant_id: str
    business_name: str
    branch_name: Optional[str]
    currency: str
    whatsapp_status: str
    display_phone_number: Optional[str]

class UsageResponse(BaseModel):
    plan_name: str
    period: str
    used: int
    limit: int
```

### New WebSocket events

Add these to `WSEventType`:

| Event | Payload | Drives |
|---|---|---|
| `conversation.updated` | `{ conversation }` (with group, handled_by, escalation) | Queue regrouping, takeover bar |
| `agent.typing` | `{ conversation_id, typing: bool }` | Typing indicator |
| `agent.step` (already declared) | `{ conversation_id, step: TraceStep }` | Trace lines appearing live |
| `message.status` (exists) | must include the real `wamid` and `status` | Read ticks |

---

## 4. Agent and webhook changes

1. **Check the takeover flag before running the agent.** In `handle_text_turn`, after saving the inbound message: if `conversation.handled_by == "owner"`, the escalation is active, or `tenant.agent_enabled` is false, then stop. Don't run the agent.
2. **Add an `escalate` tool** in `agents/customer_support/tools.py` with arguments `(reason, summary)`. It sets `conversation.escalation`, emits `conversation.updated`, and returns text telling the agent to reply "I've passed this to the restaurant." Update the prompt so refunds, complaints and requests for a human always use it.
3. **Capture the trace** with a LangChain `AsyncCallbackHandler` passed in the agent's `config["callbacks"]`. `on_tool_start` records the start time, and `on_tool_end` / `on_tool_error` append a `TraceStep` and emit `agent.step`. Attach the list to the outbound message's `agent_metadata`.
4. **Typing events:** emit `agent.typing: true` before `agent.ainvoke` and `false` after it returns, including on errors.
5. **Real wamid:** make `send_whatsapp_message` return the wamid (or `None`). Store it in `persist_outbound` / `update_outbound_status`. The existing status webhook then matches.
6. **`create_order_tool`:** compute `subtotal`, `delivery_fee` and `total_amount` on the server from the item prices and tenant settings, and don't trust the LLM's total. Set `currency`, `eta_minutes`, `source="ai_agent"` and `conversation_id`. Format money with the tenant's currency.
7. **Usage:** `$inc` the tenant's `usage_counters` after each agent reply.

---

## 5. Switching the frontend to real data

Once the backend fields exist, each mock-only field maps directly to a real one. Change the mapping functions (such as `toQueueConversation` in `hooks/console/use-queue.ts`) and leave the components alone.

| Mock field | Real source |
|---|---|
| `MockConversation.group` | `conversation.group` (computed on the server) |
| `escalated` / `escalationReason` | `escalation?.active` / `escalation?.summary` |
| `takeoverByOwner` | `handled_by === "owner"` |
| `isAgentTyping` | the `agent.typing` WebSocket event, kept in query cache state |
| `MockMessage.trace[]` | `agent_metadata.trace[]`: `duration_ms / 1000 → durationS`, `status === "ok" ? "ok" : "need"` → `resultTone`, `result_summary → result`, `JSON args → args` |
| `MockOrder.delivery_fee` / `eta_minutes` / `source` | same names on the real order |
| `KpiValue[]` | `GET /dashboard/kpis?range=today`, mapped to the four tiles |
| `TenantSummary.branch_name` / `whatsapp_connected` | `GET /tenant/mine`, `whatsapp_status === "connected"` |
| Plan meter | `GET /billing/usage` |
| `toggleTakeover` | `POST …/takeover` or `…/handback` |
| Toast "got a WhatsApp update" | show only when `customer_notified === true` |

Then set `NEXT_PUBLIC_USE_MOCKS=false`, and remove each `TODO(backend)` comment as its feature lands. The "Replay lunch rush" button stays mock-only.

---

## 6. Build order

Each phase can be shipped and tested on its own.

| Phase | Work | The dashboard gets |
|---|---|---|
| **0. Safety** | §1 fixes 1–5 | Nothing visible. Closes the token leak and the cross-tenant replies |
| **1. Takeover and escalation** | Conversation fields, the takeover, handback and resolve endpoints, the agent check, the `escalate` tool, `conversation.updated` | Real "Needs you" group, Take over / Hand back, quick replies on escalated chats |
| **2. Agent visibility** | Trace callback, `agent.step`, `agent.typing`, real wamid | Trace lines, typing indicator, read ticks |
| **3. Orders and KPIs** | Order fields, transition rules, status history, customer notification, `from`/`to` filter, `/dashboard/kpis` | Accurate rail and KPI strip, honest "customer notified" toasts |
| **4. Tenant chrome** | Tenant fields, `/tenant/mine`, `PATCH /tenant/current/agent` | Tenant switcher with names, agent on/paused/disconnected indicator |
| **5. Remaining pages** | Frontend only, since the APIs exist | Menu knowledge, Reports, Settings |
| **6. Billing** | Plans, `usage_counters`, `/billing/usage` | Plan usage meter |

Customer notifications in phase 3 are free-form WhatsApp messages. They only work within 24 hours of the customer's last message. Outside that window Meta requires an approved template, so the notification should fall back to a template or be skipped, and `customer_notified: false` should be returned.
