"""
Owner alerts: something failed or needs the owner, and they should know.

An alert is saved (so it's still there after a reload), pushed to any dashboard
that is open, and, for critical problems, sent to the restaurant's own WhatsApp
number. Recording an alert never raises, so a failed alert can't break the
thing it's reporting.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Literal, Optional

from core.whatsapp_utils import resolve_tenant_whatsapp_credentials, send_whatsapp_message

logger = logging.getLogger(__name__)

ALERTS = "owner_alerts"
Severity = Literal["info", "warning", "critical"]

# A critical alert of the same kind is sent to the owner's WhatsApp at most once in this window.
WHATSAPP_REPEAT_WINDOW = timedelta(hours=1)


def serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: v for k, v in doc.items() if k != "_id"}
    if "_id" in doc:
        out["id"] = str(doc["_id"])
    return out


async def raise_alert(
    db,
    tenant_id: str,
    kind: str,
    title: str,
    detail: str = "",
    severity: Severity = "warning",
    ref: Optional[Dict[str, Any]] = None,
) -> None:
    """Saves an alert, tells open dashboards, and for critical ones messages the owner on WhatsApp."""
    try:
        now = datetime.now(timezone.utc)
        doc = {
            "tenant_id": tenant_id,
            "kind": kind,
            "severity": severity,
            "title": title,
            "detail": detail,
            "ref": ref or {},
            "created_at": now,
            "read_at": None,
            "owner_notified_whatsapp": False,
        }

        if severity == "critical":
            doc["owner_notified_whatsapp"] = await _message_owner(db, tenant_id, kind, title, detail, now)

        inserted = await db["owner_alerts"].insert_one(doc)
        doc["_id"] = inserted.inserted_id

        from core.ws_manager import ws_manager
        from schemas.ws_events import WSEvent

        await ws_manager.broadcast_to_tenant(
            tenant_id,
            WSEvent(type="alert.new", payload={"alert": serialize(doc)}),
        )
        logger.warning(f"[alert:{severity}] {tenant_id} {kind}: {title} {detail}")
    except Exception as e:
        logger.error(f"Could not record alert {kind} for {tenant_id}: {e}")


async def _message_owner(db, tenant_id: str, kind: str, title: str, detail: str, now: datetime) -> bool:
    """Sends a critical alert to the restaurant's own number. False if skipped or failed."""
    tenant = await db["tenants"].find_one({"tenant_id": tenant_id}, {"business_phone": 1, "tenant_id": 1, "whatsapp_access_token": 1, "phone_number_id": 1})
    owner_phone = (tenant or {}).get("business_phone")
    if not owner_phone:
        return False

    recent = await db["owner_alerts"].find_one({
        "tenant_id": tenant_id,
        "kind": kind,
        "owner_notified_whatsapp": True,
        "created_at": {"$gte": now - WHATSAPP_REPEAT_WINDOW},
    })
    if recent:
        return False

    token, phone_id = resolve_tenant_whatsapp_credentials(tenant)
    text = f"Siyaf alert: {title}." + (f" {detail}" if detail else "")
    return await send_whatsapp_message(
        to_phone=owner_phone.replace("+", "").replace(" ", ""),
        text=text[:900],
        token=token,
        phone_number_id=phone_id,
    )


async def ensure_alert_indexes(db) -> None:
    await db[ALERTS].create_index([("tenant_id", 1), ("created_at", -1)], name="tenant_alerts_recent")
    await db[ALERTS].create_index([("tenant_id", 1), ("read_at", 1)], name="tenant_alerts_unread")
