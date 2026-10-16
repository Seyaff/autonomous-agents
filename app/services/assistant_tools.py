"""
The owner's agent's tools. Each one does a single thing the owner could do on a dashboard screen,
through the same service the screen uses, for this turn's business only.

Changes that are safe to undo (settings, the catalog, order progress, who handles a chat) are made right away
and reported as "old -> new". Anything that reaches customers or can't be taken back (messages, campaigns,
cancelling an order, deleting) is only proposed: it's saved as a pending action and the owner presses Confirm
in the panel to run it. The model never runs those itself.
"""

import logging
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from langchain_core.tools import tool
from pydantic import ValidationError

from core.setup_state import AgentSettings
from services.availability import MENU_ITEMS, normalize, today_for
from services.channels import channel_of
from services.conversation_state import GROUP_FILTERS, compute_group
from services.menu_view import menu_text
from services.order_service import (
    ORDER_STATUSES,
    ORDER_TRANSITIONS,
    REVENUE_EXCLUDED_STATUSES,
    customer_in_service_window,
    tenant_timezone,
)
from services.tenant_settings import TenantUpdatePayload, apply_agent_settings, apply_tenant_update, log_changes

logger = logging.getLogger(__name__)

ACTIONS = "assistant_actions"
ACTION_TTL = timedelta(minutes=30)
SOURCE = "assistant"

# Where the agent can take the owner. Values are dashboard paths.
PAGES: Dict[str, str] = {
    "home": "/dashboard",
    "inbox": "/dashboard/inbox",
    "orders": "/dashboard/orders",
    "customers": "/dashboard/customers",
    "catalog": "/dashboard/menu",
    "settings": "/dashboard/settings",
    "templates": "/dashboard/templates",
    "campaigns": "/dashboard/campaigns",
    "forms": "/dashboard/forms",
    "reports": "/dashboard/reports",
    "billing": "/dashboard/billing",
}

GROUP_NAMES = {
    "needs_you": "needs you",
    "owner_handling": "you're handling",
    "agent_handling": "agent handling",
    "resolved": "resolved",
}


@dataclass
class Turn:
    """What one turn did, for the stream and the transcript."""
    applied: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    pages: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Small readers
# ---------------------------------------------------------------------------
def current_settings(tenant: Dict[str, Any]) -> Dict[str, Any]:
    delivery = tenant.get("delivery_settings") or {}
    return {
        "business_name": tenant.get("business_name"),
        "business_description": tenant.get("business_description") or "",
        "business_phone": tenant.get("business_phone"),
        "address": tenant.get("address"),
        "currency": tenant.get("currency"),
        "timezone": tenant.get("timezone"),
        "flat_delivery_fee": delivery.get("flat_delivery_fee"),
        "avg_prep_time_minutes": delivery.get("avg_prep_time_minutes"),
        "min_order_amount": tenant.get("min_order_amount"),
        "operating_hours": tenant.get("operating_hours") or [],
        "delivery_areas": tenant.get("delivery_areas") or [],
        "payment_methods": tenant.get("payment_methods") or [],
        "order_types": tenant.get("order_types") or [],
        "reply_settings": tenant.get("agent_settings") or {},
        "agent_enabled": tenant.get("agent_enabled", True),
    }


def _money(amount: Any, currency: Optional[str]) -> str:
    try:
        value = float(amount or 0)
    except (TypeError, ValueError):
        return str(amount)
    text = f"{value:,.0f}" if value == int(value) else f"{value:,.2f}"
    return f"{currency} {text}" if currency else text


def _plain(value: Any) -> Any:
    """1500.0 reads as 1500."""
    return int(value) if isinstance(value, float) and value.is_integer() else value


def _as_utc(dt: Any) -> Optional[datetime]:
    if not isinstance(dt, datetime):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _local(dt: Any, tenant: Dict[str, Any]) -> str:
    when = _as_utc(dt)
    if not when:
        return "-"
    try:
        zone = ZoneInfo(tenant_timezone(tenant))
    except Exception:
        zone = timezone.utc
    return when.astimezone(zone).strftime("%a %d %b, %I:%M %p")


def _local_day_start(tenant: Dict[str, Any], days_back: int = 0) -> datetime:
    """Midnight in the business's timezone, days_back days ago, in UTC."""
    try:
        zone = ZoneInfo(tenant_timezone(tenant))
    except Exception:
        zone = timezone.utc
    now = datetime.now(zone)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_back)
    return start.astimezone(timezone.utc)


def _order_line(order: Dict[str, Any], tenant: Dict[str, Any]) -> str:
    items = ", ".join(f"{i.get('quantity', 1)}x {i.get('name')}" for i in order.get("items") or [])
    who = order.get("customer_name") or order.get("customer_phone")
    kind = (order.get("order_type") or "delivery").replace("_", " ")
    when = f" for {order['scheduled_for_local']}" if order.get("scheduled_for_local") else ""
    return (f"{order.get('order_id')} | {order.get('status')} | {kind}{when} | {who} | "
            f"{_money(order.get('total_amount'), order.get('currency') or tenant.get('currency'))} | "
            f"{_local(order.get('created_at'), tenant)} | {items}")


def _conversation_line(doc: Dict[str, Any]) -> str:
    contact = doc.get("customer_phone") or ""
    if channel_of(contact) == "instagram":
        contact = f"@{doc['customer_username']} (Instagram)" if doc.get("customer_username") else "Instagram"
    last = (doc.get("last_message") or {}).get("content") or ""
    if len(last) > 80:
        last = last[:77] + "..."
    unread = doc.get("unread_count") or 0
    return (f"{doc.get('conversation_id')} | {doc.get('customer_name') or 'Customer'} | {contact} | "
            f"{GROUP_NAMES.get(compute_group(doc), compute_group(doc))}"
            f"{f' | {unread} unread' if unread else ''} | last: {last}")


async def _find_items(db, tenant_id: str, name: str) -> List[Dict[str, Any]]:
    """Catalog items matching a name: the exact name if there is one, otherwise every item containing it."""
    wanted = normalize(name or "")
    if not wanted:
        return []
    rows = await db[MENU_ITEMS].find({"tenant_id": tenant_id}).to_list(length=1000)
    exact = [r for r in rows if normalize(r.get("name") or "") == wanted]
    return exact or [r for r in rows if wanted in normalize(r.get("name") or "")]


def _which_item(matches: List[Dict[str, Any]], name: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not matches:
        return None, f"No item named {name} in the catalog. Check the name with list_catalog."
    names = sorted({m.get("name") for m in matches})
    if len(names) > 1:
        return None, f"More than one item matches {name}: {', '.join(names[:10])}. Ask the owner which one."
    return matches[0], None


# ---------------------------------------------------------------------------
# Actions that wait for the owner's Confirm
# ---------------------------------------------------------------------------
Executor = Callable[[Any, Dict[str, Any], Any, Dict[str, Any]], Awaitable[Tuple[str, List[Dict[str, Any]]]]]
EXECUTORS: Dict[str, Executor] = {}


def executor(kind: str):
    def register(fn: Executor) -> Executor:
        EXECUTORS[kind] = fn
        return fn
    return register


async def propose(db, tenant_id: str, user_id: Any, turn: Turn, kind: str, args: Dict[str, Any], summary: str,
                  detail: str = "", confirm_label: str = "Confirm") -> str:
    """Saves an action for the owner to confirm, and tells the model it is waiting."""
    action = {
        "action_id": f"act_{uuid.uuid4().hex[:12]}",
        "kind": kind,
        "summary": summary,
        "detail": detail,
        "confirm_label": confirm_label,
        "status": "pending",
    }
    await db[ACTIONS].insert_one({
        **action,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "args": args,
        "created_at": datetime.now(timezone.utc),
    })
    turn.actions.append(action)
    return (f"Waiting for the owner: a card with Confirm and Cancel buttons is now showing \"{summary}\". "
            "Nothing has happened yet. In one short sentence, say what will happen when they press Confirm. "
            "Don't ask them to type yes, and don't call this tool again for the same thing.")


async def decide_action(db, tenant_id: str, user_id: Any, action_id: str, confirm: bool) -> Dict[str, Any]:
    """Runs (or drops) an action the owner confirmed (or cancelled) in the panel.
    Returns {"status", "message", "changes"}."""
    doc = await db[ACTIONS].find_one({"action_id": action_id, "tenant_id": tenant_id})
    if not doc:
        return {"status": "missing", "message": "That action wasn't found.", "changes": []}
    if doc.get("status") != "pending":
        return {"status": doc.get("status"), "message": doc.get("result") or "That was already handled.", "changes": []}

    now = datetime.now(timezone.utc)
    created = _as_utc(doc.get("created_at")) or now
    if confirm and now - created > ACTION_TTL:
        confirm = False
        outcome, message, changes = "expired", "That request expired. Ask again if you still want it.", []
    elif not confirm:
        outcome, message, changes = "cancelled", f"Cancelled: {doc['summary']}.", []
    else:
        run = EXECUTORS.get(doc["kind"])
        tenant = await db.tenants.find_one({"tenant_id": tenant_id}) or {"tenant_id": tenant_id}
        try:
            if not run:
                raise ValueError("I can't do that kind of action any more.")
            message, changes = await run(db, tenant, user_id, doc.get("args") or {})
            outcome = "done"
        except Exception as e:
            from services.owner_actions import ActionError

            reason = e.message if isinstance(e, ActionError) else str(e) if isinstance(e, ValueError) else None
            if reason is None:
                logger.exception(f"[owner-agent] action {doc['kind']} failed for {tenant_id}: {e}")
                reason = "Something went wrong."
            outcome, message, changes = "failed", f"Couldn't do it: {reason}", []

    # Claim the action, so a double press runs it once.
    claimed = await db[ACTIONS].update_one(
        {"action_id": action_id, "tenant_id": tenant_id, "status": "pending"},
        {"$set": {"status": outcome, "result": message, "decided_at": now, "decided_by": user_id}},
    )
    if not claimed.matched_count:
        return {"status": "done", "message": "That was already handled.", "changes": []}
    if changes:
        await log_changes(db, tenant_id, user_id, SOURCE, changes, now)
    return {"status": outcome, "message": message, "changes": changes}


@executor("pause_agent")
async def _run_pause_agent(db, tenant, user_id, args):
    current = tenant.get("agent_enabled", True)
    await db.tenants.update_one({"tenant_id": tenant["tenant_id"]},
                                {"$set": {"agent_enabled": False, "updated_at": datetime.now(timezone.utc)}})
    return "The agent is paused. Customers' messages still reach the inbox.", (
        [{"field": "agent_enabled", "before": current, "after": False}] if current else []
    )


@executor("message_customer")
async def _run_message_customer(db, tenant, user_id, args):
    from services.owner_actions import owner_reply

    conversation = await db["conversations"].find_one(
        {"conversation_id": args["conversation_id"], "tenant_id": tenant["tenant_id"]})
    if not conversation:
        raise ValueError("That chat no longer exists.")
    sent, _ = await owner_reply(db, tenant, conversation, args["text"], user_id)
    who = conversation.get("customer_name") or "the customer"
    if not sent:
        raise ValueError(f"the message to {who} wasn't accepted. Check the inbox.")
    return f"Sent to {who}. You're handling that chat now; hand it back to the agent when you're done.", []


@executor("cancel_order")
async def _run_cancel_order(db, tenant, user_id, args):
    from services.owner_actions import change_order_status

    order, told = await change_order_status(db, tenant, args["order_id"], "cancelled", user_id, notes=args.get("reason"))
    return (f"Order {order['order_id']} is cancelled." + (" The customer was told." if told else
            " The customer wasn't messaged, so let them know.")), []


@executor("delete_item")
async def _run_delete_item(db, tenant, user_id, args):
    result = await db[MENU_ITEMS].delete_one({"_id": args["item_id"], "tenant_id": tenant["tenant_id"]})
    if not result.deleted_count:
        raise ValueError("that item was already removed.")
    return f"{args['name']} is removed from the catalog.", [{"field": "menu.removed", "before": args["name"], "after": None}]


@executor("send_campaign")
async def _run_send_campaign(db, tenant, user_id, args):
    from services.campaigns import CampaignCreate, create_campaign, start_campaign

    campaign = await create_campaign(db, tenant, CampaignCreate(**args), user_id)
    start_campaign(db, tenant, campaign["campaign_id"])
    return f"The campaign {campaign['name']} is sending to {campaign['counts']['total']} customers. Follow it on the Campaigns page.", []


@executor("submit_template")
async def _run_submit_template(db, tenant, user_id, args):
    from services.templates import TemplateDraft, submit_template

    doc = await submit_template(db, tenant, TemplateDraft(**args))
    return f"Template {doc['name']} was sent to Meta for review. Its status now: {doc.get('status')}.", []


@executor("send_form")
async def _run_send_form(db, tenant, user_id, args):
    from services.forms import FORMS, send_form_to

    doc = await db[FORMS].find_one({"form_id": args["form_id"], "tenant_id": tenant["tenant_id"]})
    if not doc or doc.get("meta_status") != "PUBLISHED":
        raise ValueError("that form isn't published any more.")
    result = await send_form_to(db, tenant, args["phone"], doc)
    if not result.ok:
        raise ValueError(result.error_message or "WhatsApp didn't accept the form.")
    return f"The form {doc['name']} was sent.", []


# ---------------------------------------------------------------------------
# The tools
# ---------------------------------------------------------------------------
def make_tools(db, tenant_id: str, user_id: Any, turn: Turn) -> List[Any]:
    """The tools close over this turn's business and user, so the model can't reach another business."""

    async def _tenant() -> Dict[str, Any]:
        return await db.tenants.find_one({"tenant_id": tenant_id}) or {"tenant_id": tenant_id}

    async def _log(changes: List[Dict[str, Any]]) -> None:
        if changes:
            await log_changes(db, tenant_id, user_id, SOURCE, changes, datetime.now(timezone.utc))
            turn.applied.extend(changes)

    # -- Settings -------------------------------------------------------------
    @tool
    async def get_business_settings() -> dict:
        """Current settings: name, description of the business, phone, address, currency, timezone, delivery fee, prep time,
        minimum order, opening hours, delivery areas, payment methods, order types, reply settings, and whether the agent is on."""
        return current_settings(await _tenant())

    @tool
    async def update_business_settings(changes: dict) -> str:
        """Change business settings. Pass only the fields to change. Keys: business_name, business_description
        (what the business does, in plain words; pass the whole new text), business_phone, address,
        currency, timezone, flat_delivery_fee, avg_prep_time_minutes, min_order_amount, operating_hours (all 7 days,
        each {"day": "mon", "open": "12:00", "close": "23:30", "closed": false}), delivery_areas (list of text),
        payment_methods (cash_on_delivery, card_on_delivery, bank_transfer), order_types (delivery, takeaway = pickup,
        dine_in = at the business's place, booking = appointment at a set time)."""
        unknown = set(changes) - set(TenantUpdatePayload.model_fields)
        if unknown:
            return f"Not saved. Unknown setting: {', '.join(sorted(unknown))}."
        try:
            payload = TenantUpdatePayload(**changes)
        except ValidationError as e:
            return f"Not saved. {e.errors()[0]['msg']}"
        try:
            done = await apply_tenant_update(db, tenant_id, payload, user_id=user_id, source=SOURCE)
        except ValueError as e:
            return f"Not saved. {e}"
        turn.applied.extend(done)
        return "Saved." if done else "Nothing changed; those values were already set."

    @tool
    async def update_reply_settings(changes: dict) -> str:
        """Change how the customer agent replies. Keys: language ("match" to follow the customer, "en", or "roman_urdu"),
        tone ("warm", "professional" or "short"), greeting (text, or empty to clear), and escalate_on (an object with
        refund, complaint and human_requested as true/false, and large_order_over as a number or null) for the
        situations that go to the owner."""
        unknown = set(changes) - set(AgentSettings.model_fields)
        if unknown:
            return f"Not saved. Unknown setting: {', '.join(sorted(unknown))}."
        current = (await _tenant()).get("agent_settings") or {}
        merged = {**current, **changes}
        if "escalate_on" in changes:
            merged["escalate_on"] = {**(current.get("escalate_on") or {}), **(changes["escalate_on"] or {})}
        try:
            new_settings = AgentSettings(**merged)
        except ValidationError as e:
            return f"Not saved. {e.errors()[0]['msg']}"
        done = await apply_agent_settings(db, tenant_id, new_settings, user_id=user_id, source=SOURCE)
        turn.applied.extend(done)
        return "Saved." if done else "Nothing changed; those values were already set."

    @tool
    async def set_agent_enabled(enabled: bool) -> str:
        """Turn the customer agent on, or ask to pause it. Pausing stops replies to every customer, so it is shown
        to the owner as a Confirm button instead of happening right away."""
        tenant = await _tenant()
        current = tenant.get("agent_enabled", True)
        if current == enabled:
            return "Already set."
        if not enabled:
            return await propose(db, tenant_id, user_id, turn, "pause_agent", {},
                                 "Pause the agent for every customer",
                                 "Customers' messages still reach the inbox, and you reply by hand.", "Pause agent")
        await db.tenants.update_one({"tenant_id": tenant_id},
                                    {"$set": {"agent_enabled": True, "updated_at": datetime.now(timezone.utc)}})
        await _log([{"field": "agent_enabled", "before": current, "after": True}])
        return "The agent is on again."

    @tool
    async def get_channels() -> str:
        """Which channels are connected (WhatsApp, Instagram), and whether the customer agent is on."""
        tenant = await _tenant()
        wa = tenant.get("whatsapp_connected") and tenant.get("phone_number_id")
        ig = tenant.get("instagram_connected") and tenant.get("instagram_account_id")
        wa_text = "connected" if wa else "not connected"
        if tenant.get("whatsapp_last_error"):
            wa_text += f" (last error: {tenant['whatsapp_last_error']})"
        ig_text = (f"connected as @{tenant['instagram_username']}" if tenant.get("instagram_username") else "connected") if ig else "not connected"
        if tenant.get("instagram_last_error"):
            ig_text += f" (last error: {tenant['instagram_last_error']})"
        return "\n".join([
            f"WhatsApp: {wa_text}",
            f"Instagram: {ig_text}",
            f"Customer agent: {'on' if tenant.get('agent_enabled', True) else 'paused'}",
        ])

    # -- Catalog --------------------------------------------------------------
    @tool
    async def list_catalog(category: str = "") -> str:
        """What the business sells, grouped by category, with prices and what's unavailable today. Use it to match
        the owner's words to exact item names. Pass a category name to narrow it."""
        return await menu_text(db, await _tenant(), category or None) or "There is no catalog yet."

    @tool
    async def set_item_unavailable(name: str, sold_out: bool) -> str:
        """Mark an item unavailable (sold out) for today, or available again. It comes back on its own tomorrow."""
        item, problem = _which_item(await _find_items(db, tenant_id, name), name)
        if problem:
            return problem
        tenant = await _tenant()
        update = {"$set": {"sold_out_on": today_for(tenant)}} if sold_out else {"$unset": {"sold_out_on": ""}}
        await db[MENU_ITEMS].update_many({"tenant_id": tenant_id, "name": item["name"]}, update)
        await _log([{"field": "menu.sold_out", "before": None, "after": item["name"] if sold_out else None}])
        return f"{item['name']} is unavailable today." if sold_out else f"{item['name']} is available again."

    @tool
    async def add_catalog_item(name: str, price: float, category: str = "", description: str = "") -> str:
        """Add an item (product, service or dish) to the catalog with its price."""
        name = (name or "").strip()
        if len(name) < 2 or len(name) > 80:
            return "Not saved. The name must be 2 to 80 characters."
        if price is None or price < 0 or price > 1_000_000:
            return "Not saved. Give a price between 0 and 1,000,000."
        existing = [m for m in await _find_items(db, tenant_id, name) if normalize(m.get("name") or "") == normalize(name)]
        if existing:
            return f"{existing[0]['name']} is already in the catalog. Use update_catalog_item to change it."
        await db[MENU_ITEMS].insert_one({
            "tenant_id": tenant_id,
            "name": name,
            "category": category.strip() or None,
            "price": float(price),
            "description": description.strip()[:300],
            "hidden": False,
            "manual": True,
            "created_at": datetime.now(timezone.utc),
        })
        await _log([{"field": "menu.added", "before": None, "after": f"{name} ({price:g})"}])
        return f"Added {name}."

    @tool
    async def update_catalog_item(name: str, changes: dict) -> str:
        """Change one catalog item. name is the item's current name. Keys in changes: name (rename), price, category,
        description, hidden (true stops the agent offering it at all, false offers it again)."""
        allowed = {"name", "price", "category", "description", "hidden"}
        unknown = set(changes) - allowed
        if unknown:
            return f"Not saved. Unknown field: {', '.join(sorted(unknown))}."
        item, problem = _which_item(await _find_items(db, tenant_id, name), name)
        if problem:
            return problem
        clean: Dict[str, Any] = {}
        if "name" in changes:
            new_name = str(changes["name"] or "").strip()
            if len(new_name) < 2 or len(new_name) > 80:
                return "Not saved. The name must be 2 to 80 characters."
            clean["name"] = new_name
        if "price" in changes:
            try:
                price = float(changes["price"])
            except (TypeError, ValueError):
                return "Not saved. The price must be a number."
            if price < 0 or price > 1_000_000:
                return "Not saved. Give a price between 0 and 1,000,000."
            clean["price"] = price
        if "category" in changes:
            clean["category"] = str(changes["category"] or "").strip()[:60] or None
        if "description" in changes:
            clean["description"] = str(changes["description"] or "").strip()[:300]
        if "hidden" in changes:
            clean["hidden"] = bool(changes["hidden"])
        diffs = [{"field": f"menu.{k}", "before": f"{item['name']}: {_plain(item.get(k))}", "after": f"{clean.get('name', item['name'])}: {_plain(v)}"}
                 for k, v in clean.items() if item.get(k) != v]
        if not diffs:
            return "Nothing changed; those values were already set."
        await db[MENU_ITEMS].update_one({"_id": item["_id"], "tenant_id": tenant_id},
                                        {"$set": {**clean, "updated_at": datetime.now(timezone.utc)}})
        await _log(diffs)
        return "Saved."

    @tool
    async def remove_catalog_item(name: str) -> str:
        """Ask to delete an item from the catalog for good. The owner confirms with a button."""
        item, problem = _which_item(await _find_items(db, tenant_id, name), name)
        if problem:
            return problem
        return await propose(db, tenant_id, user_id, turn, "delete_item", {"item_id": item["_id"], "name": item["name"]},
                             f"Delete {item['name']} from the catalog",
                             "To hide it for a while instead, mark it unavailable or hidden.", "Delete")

    # -- Orders ---------------------------------------------------------------
    @tool
    async def find_orders(status: str = "", days: int = 1, customer: str = "", limit: int = 15) -> str:
        """Orders, newest first. status: one of pending, accepted, preparing, out_for_delivery, delivered, cancelled,
        or "open" for every order not finished yet, or empty for all. days: how many days back, counting today as 1
        (use 1 for today, 7 for this week). customer: part of a name or phone. Each line: id | status | type | customer |
        total | placed at | items."""
        tenant = await _tenant()
        query: Dict[str, Any] = {"tenant_id": tenant_id,
                                 "created_at": {"$gte": _local_day_start(tenant, max(1, min(int(days or 1), 365)) - 1)}}
        if status == "open":
            query["status"] = {"$in": ["pending", "accepted", "preparing", "out_for_delivery"]}
        elif status:
            if status not in ORDER_STATUSES:
                return f"Unknown status {status}. Use one of: {', '.join(ORDER_STATUSES)}, or open."
            query["status"] = status
        rows = await db["orders"].find(query).sort("created_at", -1).to_list(length=1000)
        if customer:
            needle = customer.strip().lower()
            rows = [o for o in rows if needle in (o.get("customer_name") or "").lower() or needle in (o.get("customer_phone") or "")]
        if not rows:
            return "No orders match."
        shown = rows[: max(1, min(int(limit or 15), 50))]
        more = f"\n...and {len(rows) - len(shown)} more." if len(rows) > len(shown) else ""
        return f"{len(rows)} order(s):\n" + "\n".join(_order_line(o, tenant) for o in shown) + more

    @tool
    async def get_order(order_id: str) -> str:
        """Everything about one order: items, totals, customer, address, payment, notes and its status history."""
        tenant = await _tenant()
        order = await db["orders"].find_one({"order_id": order_id.strip(), "tenant_id": tenant_id})
        if not order:
            return f"No order {order_id}."
        currency = order.get("currency") or tenant.get("currency")
        lines = [
            _order_line(order, tenant),
            f"Customer: {order.get('customer_name') or '-'} ({order.get('customer_phone')})"
            + (f", contact {order['contact_phone']}" if order.get("contact_phone") else ""),
            f"Address: {order['delivery_address']}" if order.get("delivery_address") else "",
            "Items: " + "; ".join(f"{i.get('quantity', 1)}x {i.get('name')} @ {_money(i.get('price'), currency)}"
                                  + (f" ({i['notes']})" if i.get("notes") else "") for i in order.get("items") or []),
            f"Subtotal {_money(order.get('subtotal'), currency)}, delivery {_money(order.get('delivery_fee'), currency)}, "
            f"total {_money(order.get('total_amount'), currency)}, payment {order.get('payment_method') or '-'}",
            f"Customer notes: {order['customer_notes']}" if order.get("customer_notes") else "",
            f"Your notes: {order['admin_notes']}" if order.get("admin_notes") else "",
            "History: " + "; ".join(f"{h.get('status')} {_local(h.get('at'), tenant)} by {h.get('by')}"
                                    for h in order.get("status_history") or []),
            "Can move to: " + (", ".join(sorted(ORDER_TRANSITIONS.get(order.get("status"), ()))) or "nothing (finished)"),
            f"Chat: {order['conversation_id']}" if order.get("conversation_id") else "",
        ]
        return "\n".join(line for line in lines if line)

    @tool
    async def update_order_status(order_id: str, status: str, note: str = "") -> str:
        """Move an order on: accepted, preparing, out_for_delivery, delivered. The customer gets the usual update.
        Cancelling is shown to the owner as a Confirm button. Check get_order for the moves allowed."""
        from services.owner_actions import ActionError, change_order_status

        order_id = order_id.strip()
        status = status.strip().lower()
        if status == "cancelled":
            order = await db["orders"].find_one({"order_id": order_id, "tenant_id": tenant_id})
            if not order:
                return f"No order {order_id}."
            if "cancelled" not in ORDER_TRANSITIONS.get(order.get("status"), ()):
                return f"Order {order_id} is {order.get('status')} and can't be cancelled."
            who = order.get("customer_name") or order.get("customer_phone")
            return await propose(db, tenant_id, user_id, turn, "cancel_order", {"order_id": order_id, "reason": note or None},
                                 f"Cancel order {order_id} for {who}",
                                 "The customer is told it's cancelled.", "Cancel order")
        try:
            order, told = await change_order_status(db, await _tenant(), order_id, status, user_id, notes=note or None)
        except ActionError as e:
            return f"Not changed. {e.message}"
        turn.applied.append({"field": f"order.{order_id}", "before": order["status_history"][-2]["status"]
                             if len(order.get("status_history") or []) > 1 else None, "after": status})
        return f"Order {order_id} is now {status}." + (" The customer was told." if told else " The customer wasn't messaged (outside the reply window).")

    # -- Numbers --------------------------------------------------------------
    @tool
    async def sales_summary(days: int = 1) -> str:
        """Sales over the last N days counting today as 1 (1 = today, 7 = this week, 30 = this month): number of orders,
        revenue, average order, orders by status and type, best sellers, best day and busiest hours, compared with the
        N days before."""
        tenant = await _tenant()
        days = max(1, min(int(days or 1), 365))
        start = _local_day_start(tenant, days - 1)
        before = _local_day_start(tenant, 2 * days - 1)
        rows = await db["orders"].find({"tenant_id": tenant_id, "created_at": {"$gte": before}}).to_list(length=20000)
        current = [o for o in rows if (_as_utc(o.get("created_at")) or start) >= start]
        previous = [o for o in rows if (_as_utc(o.get("created_at")) or start) < start]
        currency = tenant.get("currency")

        def revenue(orders):
            return sum(float(o.get("total_amount") or 0) for o in orders if o.get("status") not in REVENUE_EXCLUDED_STATUSES)

        counted = [o for o in current if o.get("status") not in REVENUE_EXCLUDED_STATUSES]
        rev, prev_rev = revenue(current), revenue(previous)
        lines = [
            f"Period: last {days} day(s) since {_local(start, tenant)}",
            f"Orders: {len(current)} (before: {len(previous)})",
            f"Revenue (accepted onward): {_money(rev, currency)} (before: {_money(prev_rev, currency)})",
            f"Average order: {_money(rev / len(counted), currency) if counted else '-'}",
            "By status: " + (", ".join(f"{k} {v}" for k, v in Counter(o.get('status') for o in current).most_common()) or "-"),
            "By type: " + (", ".join(f"{(k or 'delivery').replace('_', ' ')} {v}" for k, v in Counter(o.get('order_type') for o in current).most_common()) or "-"),
        ]
        items: Counter = Counter()
        for o in counted:
            for i in o.get("items") or []:
                items[i.get("name")] += int(i.get("quantity") or 1)
        if items:
            lines.append("Best sellers (accepted orders only, not pending or cancelled): " + ", ".join(f"{n} x{q}" for n, q in items.most_common(8)))
        try:
            zone = ZoneInfo(tenant_timezone(tenant))
        except Exception:
            zone = timezone.utc
        stamps = [(_as_utc(o.get("created_at")) or start).astimezone(zone) for o in current]
        if stamps and days > 1:
            best_day, n = Counter(s.strftime("%a %d %b") for s in stamps).most_common(1)[0]
            lines.append(f"Busiest day: {best_day} ({n} orders)")
        if stamps:
            hours = Counter(s.hour for s in stamps).most_common(3)
            lines.append("Busiest hours: " + ", ".join(f"{h:02d}:00 ({n})" for h, n in hours))
        customers = {o.get("customer_phone") for o in current}
        lines.append(f"Customers who ordered: {len(customers)}")
        return "\n".join(lines)

    @tool
    async def find_customers(search: str = "", min_orders: int = 0, not_ordered_for_days: int = 0, limit: int = 15) -> str:
        """Customers, from their orders: name, contact, orders, total spent, last order. search matches a name or phone.
        min_orders keeps regulars. not_ordered_for_days keeps people who haven't ordered in that many days."""
        tenant = await _tenant()
        rows = await db["orders"].find({"tenant_id": tenant_id}).sort("created_at", -1).to_list(length=20000)
        people: Dict[str, Dict[str, Any]] = {}
        for o in rows:
            p = people.setdefault(o.get("customer_phone"), {"name": o.get("customer_name"), "orders": 0, "spent": 0.0, "last": o.get("created_at")})
            p["orders"] += 1
            if o.get("status") not in REVENUE_EXCLUDED_STATUSES:
                p["spent"] += float(o.get("total_amount") or 0)
        cutoff = datetime.now(timezone.utc) - timedelta(days=not_ordered_for_days) if not_ordered_for_days else None
        needle = (search or "").strip().lower()
        found = [
            (phone, p) for phone, p in people.items()
            if (not needle or needle in (p["name"] or "").lower() or needle in (phone or ""))
            and p["orders"] >= (min_orders or 0)
            and (not cutoff or (_as_utc(p["last"]) or cutoff) < cutoff)
        ]
        if not found:
            return "No customers match."
        found.sort(key=lambda x: -x[1]["spent"])
        shown = found[: max(1, min(int(limit or 15), 50))]
        more = f"\n...and {len(found) - len(shown)} more." if len(found) > len(shown) else ""
        return f"{len(found)} customer(s):\n" + "\n".join(
            f"{p['name'] or '-'} | {phone} | {p['orders']} order(s) | {_money(p['spent'], tenant.get('currency'))} | last {_local(p['last'], tenant)}"
            for phone, p in shown) + more

    # -- Inbox ----------------------------------------------------------------
    @tool
    async def find_conversations(group: str = "", search: str = "", limit: int = 15) -> str:
        """Customer chats, most recent first. group: needs_you (escalated to the owner), owner_handling, agent_handling,
        resolved, or empty for all. search matches a name, phone or Instagram handle. Each line: id | name | contact |
        group | unread | last message."""
        query: Dict[str, Any] = {"tenant_id": tenant_id}
        if group:
            if group not in GROUP_FILTERS:
                return f"Unknown group {group}. Use one of: {', '.join(GROUP_FILTERS)}."
            query.update(GROUP_FILTERS[group])
        rows = await db["conversations"].find(query).sort("last_activity_at", -1).to_list(length=500)
        if search:
            needle = search.strip().lower().lstrip("@")
            rows = [c for c in rows if any(needle in (c.get(k) or "").lower() for k in ("customer_name", "customer_phone", "customer_username"))]
        if not rows:
            return "No chats match."
        shown = rows[: max(1, min(int(limit or 15), 50))]
        more = f"\n...and {len(rows) - len(shown)} more." if len(rows) > len(shown) else ""
        return f"{len(rows)} chat(s):\n" + "\n".join(_conversation_line(c) for c in shown) + more

    @tool
    async def read_conversation(conversation_id: str, last: int = 15) -> str:
        """The latest messages in one chat, oldest first, with who sent each (customer, agent, owner), plus whether a
        free-form message can still be sent (the 24-hour window)."""
        tenant = await _tenant()
        conversation = await db["conversations"].find_one({"conversation_id": conversation_id.strip(), "tenant_id": tenant_id})
        if not conversation:
            return f"No chat {conversation_id}."
        messages = await db["messages"].find({"conversation_id": conversation["conversation_id"]}).sort("created_at", -1).to_list(
            length=max(1, min(int(last or 15), 40)))
        messages.reverse()
        names = {"customer": conversation.get("customer_name") or "Customer", "agent": "Agent", "human": "Owner", "system": "System"}
        open_window = await customer_in_service_window(db, tenant_id, conversation["customer_phone"])
        escalation = conversation.get("escalation") or {}
        head = [
            _conversation_line(conversation),
            f"Handled by: {conversation.get('handled_by') or 'agent'}"
            + (f". Escalated: {escalation.get('reason')}" if escalation.get("active") and escalation.get("reason") else ""),
            f"Reply window: {'open' if open_window else 'closed (more than 24 hours since they wrote)'}",
        ]
        body = [f"[{_local(m.get('created_at'), tenant)}] {names.get(m.get('sender'), m.get('sender'))}: {m.get('content')}" for m in messages]
        return "\n".join(head + ["---"] + (body or ["(no messages)"]))

    @tool
    async def message_customer(conversation_id: str, text: str) -> str:
        """Ask to send the owner's message to a customer in their chat. It is shown to the owner as a Confirm button
        with the exact text, and only sent when they confirm. Write the text the way the owner would."""
        conversation = await db["conversations"].find_one({"conversation_id": conversation_id.strip(), "tenant_id": tenant_id})
        if not conversation:
            return f"No chat {conversation_id}."
        text = (text or "").strip()
        if not text:
            return "Write the message first."
        if len(text) > 4000:
            return "That message is too long. Keep it under 4000 characters."
        if not await customer_in_service_window(db, tenant_id, conversation["customer_phone"]):
            from services.owner_actions import window_closed_message

            return "Can't send. " + window_closed_message(conversation["customer_phone"])
        who = conversation.get("customer_name") or "the customer"
        return await propose(db, tenant_id, user_id, turn, "message_customer",
                             {"conversation_id": conversation["conversation_id"], "text": text},
                             f"Send to {who}", text, "Send")

    @tool
    async def set_chat_handler(conversation_id: str, handler: str) -> str:
        """Who answers a customer: "owner" takes the chat over (the agent stops replying to them), "agent" hands it back
        to the agent (and clears its needs-you flag)."""
        from services.owner_actions import set_handover

        if handler not in ("owner", "agent"):
            return 'handler must be "owner" or "agent".'
        conversation = await db["conversations"].find_one({"conversation_id": conversation_id.strip(), "tenant_id": tenant_id})
        if not conversation:
            return f"No chat {conversation_id}."
        before = conversation.get("handled_by") or "agent"
        if before == handler and not (handler == "agent" and (conversation.get("escalation") or {}).get("active")):
            return "Already set."
        await set_handover(tenant_id, conversation["conversation_id"], handler, user_id)
        turn.applied.append({"field": "chat.handled_by", "before": f"{conversation.get('customer_name') or 'chat'}: {before}",
                             "after": f"{conversation.get('customer_name') or 'chat'}: {handler}"})
        return "You're handling that chat now." if handler == "owner" else "The agent is handling that chat again."

    @tool
    async def clear_needs_you(conversation_id: str) -> str:
        """Clear a chat's "needs you" flag without changing who handles it."""
        from services.owner_actions import resolve_escalation

        conversation = await db["conversations"].find_one({"conversation_id": conversation_id.strip(), "tenant_id": tenant_id})
        if not conversation:
            return f"No chat {conversation_id}."
        if not (conversation.get("escalation") or {}).get("active"):
            return "That chat doesn't need you."
        await resolve_escalation(tenant_id, conversation["conversation_id"], user_id)
        turn.applied.append({"field": "chat.needs_you", "before": conversation.get("customer_name") or "chat", "after": None})
        return "Cleared."

    # -- Templates, campaigns and forms -----------------------------------------
    @tool
    async def list_templates(status: str = "") -> str:
        """WhatsApp message templates as last synced from Meta: name, language, category, status, variables and body.
        status: APPROVED, PENDING or REJECTED to narrow it."""
        from services.templates import TEMPLATES

        query: Dict[str, Any] = {"tenant_id": tenant_id}
        if status:
            query["status"] = status.upper()
        rows = await db[TEMPLATES].find(query).sort("name", 1).to_list(length=200)
        if not rows:
            return "No templates yet." if not status else f"No {status.lower()} templates."
        return "\n".join(
            f"{t['name']} ({t.get('language')}) | {t.get('category')} | {t.get('status')}"
            + (f" ({t['rejected_reason']})" if t.get("rejected_reason") else "")
            + f" | {t.get('body_variables', 0)} value(s) | {(t.get('body_text') or '')[:160]}"
            for t in rows)

    @tool
    async def create_template(name: str, category: str, body: str, body_examples: List[str], language: str = "en",
                              header_text: str = "", footer: str = "", quick_replies: List[str] = []) -> str:  # noqa: B006
        """Ask to submit a new WhatsApp template to Meta for review (the owner confirms with a button). name: lowercase
        with underscores. category: MARKETING (offers, news) or UTILITY (order or account updates). body: the text,
        with {{1}}, {{2}} for values that change, never at the very start or end. body_examples: one example per value.
        quick_replies: up to 3 button labels."""
        from services.templates import TemplateDraft

        args = {
            "name": name, "category": category.upper(), "language": language, "body": body, "body_examples": body_examples,
            "header_text": header_text or None, "footer": footer or None,
            "buttons": [{"type": "QUICK_REPLY", "text": q} for q in quick_replies or []],
        }
        try:
            draft = TemplateDraft(**args)
        except (ValidationError, ValueError) as e:
            msg = e.errors()[0]["msg"] if isinstance(e, ValidationError) else str(e)
            return f"Not valid yet: {msg}"
        return await propose(db, tenant_id, user_id, turn, "submit_template", draft.model_dump(),
                             f"Submit template {draft.name} for review", draft.body, "Submit")

    @tool
    async def list_campaigns() -> str:
        """Broadcast campaigns, newest first, with their status and how many were sent, delivered, read and failed."""
        from services.campaigns import CAMPAIGNS

        rows = await db[CAMPAIGNS].find({"tenant_id": tenant_id}).sort("created_at", -1).to_list(length=20)
        if not rows:
            return "No campaigns yet."
        tenant = await _tenant()
        return "\n".join(
            f"{c['name']} | {c.get('template_name')} | {c.get('status')} | {_local(c.get('created_at'), tenant)} | "
            + ", ".join(f"{k} {v}" for k, v in (c.get("counts") or {}).items())
            for c in rows)

    @tool
    async def send_campaign(name: str, template_name: str, values: List[str] = [], audience: str = "all",  # noqa: B006
                            days: int = 0, phones: List[str] = [], language: str = "") -> str:  # noqa: B006
        """Ask to send an approved template to many customers at once (the owner confirms with a button). values: one per
        template value, in order; write "{customer_name}" to use each customer's name. audience: "all" (every customer),
        "ordered_within_days" (with days), or "phones" (with phones). Customers who replied STOP are skipped."""
        from services.campaigns import Audience, CampaignCreate, resolve_audience
        from services.templates import TEMPLATES, sendable

        query: Dict[str, Any] = {"tenant_id": tenant_id, "name": template_name.strip()}
        if language:
            query["language"] = language
        doc = await db[TEMPLATES].find_one(query)
        ok, why = sendable(doc)
        if not ok:
            return f"Can't send: {why}"
        params = [{"kind": "customer_name", "value": ""} if v.strip() == "{customer_name}" else {"kind": "text", "value": v}
                  for v in values or []]
        try:
            payload = CampaignCreate(
                name=name, template_name=doc["name"], language=doc["language"], body_params=params,
                audience=Audience(kind=audience, days=days or None, phones=phones or []),
            )
        except (ValidationError, ValueError) as e:
            msg = e.errors()[0]["msg"] if isinstance(e, ValidationError) else str(e)
            return f"Not valid yet: {msg}"
        if len(payload.body_params) != doc.get("body_variables", 0) or doc.get("header_variables", 0):
            return (f"The template {doc['name']} needs {doc.get('body_variables', 0)} value(s)"
                    + (" and a header value, which only the Campaigns page can fill" if doc.get("header_variables") else "") + ".")
        recipients, skipped = await resolve_audience(db, tenant_id, payload.audience)
        if not recipients:
            return "No customers match that audience." + (" Everyone in it has opted out." if skipped else "")
        from services.templates import render

        preview = render(doc, [p.value if p.kind == "text" else (recipients[0].get("name") or "there") for p in payload.body_params])
        return await propose(db, tenant_id, user_id, turn, "send_campaign", payload.model_dump(),
                             f"Send {doc['name']} to {len(recipients)} customer(s)"
                             + (f" ({skipped} opted out, skipped)" if skipped else ""), preview, "Send campaign")

    @tool
    async def list_forms() -> str:
        """The owner's WhatsApp forms: name, purpose, status and how many responses each has."""
        from services.forms import FORMS

        rows = await db[FORMS].find({"tenant_id": tenant_id}).to_list(length=50)
        if not rows:
            return "No forms yet."
        return "\n".join(f"{f['form_id']} | {f['name']} | {f.get('meta_status') or f.get('status')} | "
                         f"{f.get('responses', 0)} response(s) | {f.get('purpose') or ''}" for f in rows)

    @tool
    async def send_form(form: str, conversation_id: str) -> str:
        """Ask to send a published form to the customer in a WhatsApp chat (the owner confirms with a button).
        form: the form's name or id."""
        from services.forms import find_published

        doc = await find_published(db, tenant_id, form)
        if not doc:
            return f"No published form called {form}. Check list_forms."
        conversation = await db["conversations"].find_one({"conversation_id": conversation_id.strip(), "tenant_id": tenant_id})
        if not conversation:
            return f"No chat {conversation_id}."
        if channel_of(conversation["customer_phone"]) != "whatsapp":
            return "Forms only work on WhatsApp."
        if not await customer_in_service_window(db, tenant_id, conversation["customer_phone"]):
            return "Can't send: it's been more than 24 hours since this customer wrote."
        who = conversation.get("customer_name") or "the customer"
        return await propose(db, tenant_id, user_id, turn, "send_form",
                             {"form_id": doc["form_id"], "phone": conversation["customer_phone"]},
                             f"Send the form {doc['name']} to {who}", doc.get("body") or "", "Send form")

    # -- Moving around --------------------------------------------------------
    @tool
    async def open_page(page: str, conversation_id: str = "") -> str:
        """Take the owner to a dashboard page, only when they ask to see or go somewhere. page: home, inbox, orders,
        customers, catalog, settings, templates, campaigns, forms, reports, billing. With page inbox, pass
        conversation_id to open one chat."""
        href = PAGES.get(page.strip().lower())
        if not href:
            return f"Unknown page. Use one of: {', '.join(PAGES)}."
        if href == PAGES["inbox"] and conversation_id:
            href = f"{href}/{conversation_id.strip()}"
        turn.pages.append(href)
        return f"Opened {page}."

    return [
        get_business_settings, update_business_settings, update_reply_settings, set_agent_enabled, get_channels,
        list_catalog, set_item_unavailable, add_catalog_item, update_catalog_item, remove_catalog_item,
        find_orders, get_order, update_order_status, sales_summary, find_customers,
        find_conversations, read_conversation, message_customer, set_chat_handler, clear_needs_you,
        list_templates, create_template, list_campaigns, send_campaign, list_forms, send_form,
        open_page,
    ]


async def ensure_assistant_indexes(db) -> None:
    await db[ACTIONS].create_index("action_id", unique=True, name="uniq_action_id")
    # Old actions are dropped after a week; the conversation keeps their summary.
    await db[ACTIONS].create_index("created_at", expireAfterSeconds=7 * 24 * 3600, name="ttl_created_at")
    await db["assistant_messages"].create_index([("tenant_id", 1), ("user_id", 1), ("at", -1)], name="owner_transcript")
