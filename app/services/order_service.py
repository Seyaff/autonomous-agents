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
    # Pickup, in-person and booked orders are done without a delivery leg.
    "preparing": frozenset({"out_for_delivery", "delivered", "cancelled"}),
    "out_for_delivery": frozenset({"delivered"}),
    "delivered": frozenset(),
    "cancelled": frozenset(),
}

# Revenue counts orders the business has accepted, not ones still waiting or dropped.
REVENUE_EXCLUDED_STATUSES = ("pending", "cancelled")

DEFAULT_DELIVERY_SETTINGS = {"flat_delivery_fee": 0.0, "avg_prep_time_minutes": 30}
DEFAULT_TIMEZONE = "Asia/Karachi"

# Meta only allows free-form messages within 24h of the customer's last message.
WHATSAPP_SERVICE_WINDOW = timedelta(hours=24)

STATUS_NOTICE = {
    "accepted": "Your order {order_id} has been accepted.",
    "preparing": "Your order {order_id} is being prepared.",
    "out_for_delivery": "Your order {order_id} is on the way.",
    "delivered": "Your order {order_id} has been delivered. Thank you!",
    "cancelled": "Your order {order_id} has been cancelled.",
}

# A booking reads differently: nothing is prepared or delivered.
BOOKING_STATUS_NOTICE = {
    "accepted": "Your booking {order_id} is confirmed.",
    "delivered": "Thanks for coming in. Booking {order_id} is complete.",
    "cancelled": "Your booking {order_id} has been cancelled.",
}

# Pickup and in-person orders aren't delivered; "delivered" means handed over.
HANDOVER_STATUS_NOTICE = {
    **STATUS_NOTICE,
    "out_for_delivery": "Your order {order_id} is ready.",
    "delivered": "Your order {order_id} is complete. Thank you!",
}


def status_notice(order: Dict[str, Any], new_status: str) -> Optional[str]:
    """The message the customer gets when their order moves to new_status, if any."""
    kind = order.get("order_type") or "delivery"
    if kind == "booking":
        table = BOOKING_STATUS_NOTICE
    elif kind == "delivery":
        table = STATUS_NOTICE
    else:
        table = HANDOVER_STATUS_NOTICE
    notice = table.get(new_status)
    return notice.format(order_id=order.get("order_id", "")) if notice else None


class InvalidTransition(Exception):
    pass


def is_valid_transition(current: str, new: str) -> bool:
    return new in ORDER_TRANSITIONS.get(current, frozenset())


def delivery_settings_for(tenant: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    stored = (tenant or {}).get("delivery_settings") or {}
    return {**DEFAULT_DELIVERY_SETTINGS, **stored}


def tenant_timezone(tenant: Optional[Dict[str, Any]]) -> str:
    return (tenant or {}).get("timezone") or DEFAULT_TIMEZONE


def compute_totals(
    items: List[Dict[str, Any]],
    tenant: Optional[Dict[str, Any]],
    order_type: str = "delivery",
) -> Tuple[float, float, float, int]:
    """Returns (subtotal, delivery_fee, total, eta_minutes) for a list of items.

    Each item needs `price` and `quantity`. Rounding is to two decimals.
    The delivery fee only applies to delivery orders.
    """
    settings = delivery_settings_for(tenant)
    subtotal = round(sum(float(i["price"]) * int(i["quantity"]) for i in items), 2)
    delivery_fee = round(float(settings["flat_delivery_fee"]), 2) if order_type == "delivery" else 0.0
    total = round(subtotal + delivery_fee, 2)
    eta = int(settings["avg_prep_time_minutes"])
    return subtotal, delivery_fee, total, eta


BOOKING_FORMAT = "%Y-%m-%d %H:%M"


def parse_booking_time(value: str, tz_name: str) -> datetime:
    """Reads "YYYY-MM-DD HH:MM" in the business's own timezone. Returns it timezone-aware, in that zone.
    Raises ValueError with a message the agent can act on."""
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    text = (value or "").strip().replace("T", " ")[:16]
    try:
        naive = datetime.strptime(text, BOOKING_FORMAT)
    except ValueError:
        raise ValueError(f"Booking time must be YYYY-MM-DD HH:MM, got {value!r}.")
    try:
        zone = ZoneInfo(tz_name or "UTC")
    except ZoneInfoNotFoundError:
        zone = ZoneInfo("UTC")
    return naive.replace(tzinfo=zone)


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

    Outside the 24h window only an approved template can go. If the business has set up
    its order-update template, that is sent; otherwise nothing is, and the caller gets
    False so it can say so honestly.
    """
    text = status_notice(order, new_status)
    if not text:
        return False

    tenant_id = tenant["tenant_id"]
    phone = order.get("customer_phone")
    if not phone:
        return False

    if not await customer_in_service_window(db, tenant_id, phone):
        # Templates exist only on WhatsApp. Instagram has no way past its 24-hour window.
        if phone.startswith("ig:"):
            return False
        return await _notify_with_template(db, tenant, order, new_status)

    from services.channels import send_text_to

    result = await send_text_to(tenant, phone, text, db)
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


async def _notify_with_template(db, tenant: Dict[str, Any], order: Dict[str, Any], new_status: str) -> bool:
    """The update outside the 24h window, through the business's order-update template."""
    from services.templates import order_update_phrase, order_update_template, send_template_message, sendable

    order_id = order.get("order_id", "")
    phrase = order_update_phrase(order, new_status)
    doc = await order_update_template(db, tenant)
    ok, why = sendable(doc)
    if not phrase or not ok:
        logger.info(f"Order {order_id} status not sent: outside 24h window and no approved update template ({why})")
        return False

    params = [
        (order.get("customer_name") or "there").split(" ")[0],
        order_id,
        tenant.get("business_name") or "us",
        phrase,
    ]
    try:
        result, _ = await send_template_message(db, tenant, order["customer_phone"], doc, params, sender="system")
    except ValueError as e:
        logger.warning(f"Order {order_id} update template not sent: {e}")
        return False
    if not result.ok:
        from services.alerts import raise_alert

        await raise_alert(
            db,
            tenant["tenant_id"],
            kind="status_update_not_sent",
            title=f"Order {order_id} update wasn't sent",
            detail=f"The customer wasn't told it is now {new_status}. {result.error_message or ''}".strip(),
            severity="critical" if result.auth_error else "warning",
            ref={"order_id": order_id},
        )
    return result.ok


def parse_range_bound(value: str, tz_name: str) -> datetime:
    """Parses an ISO datetime. Naive values are read in the tenant's timezone.

    Returns a UTC datetime, so it can be compared with stored created_at values.
    """
    from zoneinfo import ZoneInfo

    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(tz_name))
    return dt.astimezone(timezone.utc)
