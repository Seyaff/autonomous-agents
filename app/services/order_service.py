"""
Order rules shared by the agent and the owner dashboard.

Totals are computed here on the server, never taken from the LLM. Status
moves are checked against ORDER_TRANSITIONS, so the rail, the API and the
agent can't disagree about what a legal change is.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.whatsapp_utils import resolve_tenant_whatsapp_credentials, send_text, send_whatsapp_message

logger = logging.getLogger(__name__)

ORDER_STATUSES = ("pending", "accepted", "preparing", "out_for_delivery", "delivered", "cancelled")

ORDER_TRANSITIONS: Dict[str, frozenset] = {
    "pending": frozenset({"accepted", "cancelled"}),
    "accepted": frozenset({"preparing", "cancelled"}),
    "preparing": frozenset({"out_for_delivery", "cancelled"}),
    "out_for_delivery": frozenset({"delivered"}),
    "delivered": frozenset(),
    "cancelled": frozenset(),
}

# Revenue counts orders the restaurant has accepted, not ones still waiting or dropped.
REVENUE_EXCLUDED_STATUSES = ("pending", "cancelled")

DEFAULT_DELIVERY_SETTINGS = {"flat_delivery_fee": 0.0, "avg_prep_time_minutes": 30}
DEFAULT_TIMEZONE = "Asia/Karachi"

# Meta only allows free-form messages within 24h of the customer's last message.
WHATSAPP_SERVICE_WINDOW = timedelta(hours=24)

STATUS_NOTICE = {
    "accepted": "Your order {order_id} has been accepted.",
    "preparing": "Your order {order_id} is being prepared.",
    "out_for_delivery": "Your order {order_id} is on the way.",
    "delivered": "Your order {order_id} has been delivered. Enjoy your meal!",
    "cancelled": "Your order {order_id} has been cancelled.",
}


class InvalidTransition(Exception):
    pass


def is_valid_transition(current: str, new: str) -> bool:
    return new in ORDER_TRANSITIONS.get(current, frozenset())


def delivery_settings_for(tenant: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    stored = (tenant or {}).get("delivery_settings") or {}
    return {**DEFAULT_DELIVERY_SETTINGS, **stored}


def tenant_timezone(tenant: Optional[Dict[str, Any]]) -> str:
    return (tenant or {}).get("timezone") or DEFAULT_TIMEZONE


def compute_totals(items: List[Dict[str, Any]], tenant: Optional[Dict[str, Any]]) -> Tuple[float, float, float, int]:
    """Returns (subtotal, delivery_fee, total, eta_minutes) for a list of items.

    Each item needs `price` and `quantity`. Rounding is to two decimals.
    """
    settings = delivery_settings_for(tenant)
    subtotal = round(sum(float(i["price"]) * int(i["quantity"]) for i in items), 2)
    delivery_fee = round(float(settings["flat_delivery_fee"]), 2)
    total = round(subtotal + delivery_fee, 2)
    eta = int(settings["avg_prep_time_minutes"])
    return subtotal, delivery_fee, total, eta


def initial_status_entry(now: datetime, by: str = "agent", by_user_id: Optional[str] = None) -> Dict[str, Any]:
    return {
        "status": "pending",
        "at": now,
        "by": by,
        "by_user_id": by_user_id,
        "customer_notified": False,
    }


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def customer_in_service_window(db, tenant_id: str, customer_phone: str, now: Optional[datetime] = None) -> bool:
    """True if the customer messaged us within the last 24 hours."""
    now = now or datetime.now(timezone.utc)
    last = await db["messages"].find_one(
        {"tenant_id": tenant_id, "sender": "customer", "sender_phone": customer_phone},
        sort=[("created_at", -1)],
    )
    if not last or not last.get("created_at"):
        return False
    return now - _as_utc(last["created_at"]) <= WHATSAPP_SERVICE_WINDOW


async def notify_customer_status(
    db,
    tenant: Dict[str, Any],
    order: Dict[str, Any],
    new_status: str,
) -> bool:
    """Sends the customer a status update when Meta allows it. Returns whether it was sent.

    Outside the 24h window nothing is sent (a template would be needed), and
    the caller gets False so it can say so honestly.
    """
    notice = STATUS_NOTICE.get(new_status)
    if not notice:
        return False

    tenant_id = tenant["tenant_id"]
    phone = order.get("customer_phone")
    if not phone:
        return False

    if not await customer_in_service_window(db, tenant_id, phone):
        logger.info(f"Order {order.get('order_id')} status not sent: outside 24h window for {phone}")
        return False

    token, phone_number_id = resolve_tenant_whatsapp_credentials(tenant)
    text = notice.format(order_id=order.get("order_id", ""))
    result = await send_text(
        to_phone=phone,
        text=text,
        token=token,
        phone_number_id=phone_number_id,
    )
    sent = result.ok
    if not sent:
        from services.alerts import raise_alert

        await raise_alert(
            db,
            tenant_id,
            kind="status_update_not_sent",
            title=f"Order {order.get('order_id', '')} update wasn't sent",
            detail=f"The customer wasn't told it is now {new_status}. {result.error_message or ''}".strip(),
            severity="critical" if result.auth_error else "warning",
            ref={"order_id": order.get("order_id")},
        )
    if sent:
        from services.message_service import message_service

        conversation = await db["conversations"].find_one({"tenant_id": tenant_id, "customer_phone": phone})
        if conversation:
            await message_service.persist_outbound(
                conversation_id=conversation["conversation_id"],
                tenant_id=tenant_id,
                content=text,
                sender="system",
            )
    return sent


def parse_range_bound(value: str, tz_name: str) -> datetime:
    """Parses an ISO datetime. Naive values are read in the tenant's timezone.

    Returns a UTC datetime, so it can be compared with stored created_at values.
    """
    from zoneinfo import ZoneInfo

    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(tz_name))
    return dt.astimezone(timezone.utc)
