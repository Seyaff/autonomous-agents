"""
Saving restaurant settings. The settings screens and the owner assistant both save through here,
so the same checks apply, and every change is written to the change log with what it was before.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel

from core.setup_state import AgentSettings, DayHours

CHANGE_LOG = "settings_changes"


class TenantUpdatePayload(BaseModel):
    business_name: Optional[str] = None
    business_phone: Optional[str] = None
    address: Optional[str] = None
    currency: Optional[str] = None
    flat_delivery_fee: Optional[float] = None
    avg_prep_time_minutes: Optional[int] = None
    timezone: Optional[str] = None
    operating_hours: Optional[List[DayHours]] = None
    min_order_amount: Optional[float] = None
    delivery_areas: Optional[List[str]] = None
    payment_methods: Optional[List[Literal["cash_on_delivery", "card_on_delivery", "bank_transfer"]]] = None
    order_types: Optional[List[Literal["delivery", "takeaway", "dine_in"]]] = None


def _dig(doc: Dict[str, Any], path: str) -> Any:
    value: Any = doc
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


async def log_changes(db, tenant_id: str, user_id: Optional[str], source: str, changes: List[Dict[str, Any]], now: datetime) -> None:
    for change in changes:
        await db[CHANGE_LOG].insert_one({
            "tenant_id": tenant_id,
            "user_id": user_id,
            "source": source,
            "field": change["field"],
            "before": change["before"],
            "after": change["after"],
            "at": now,
        })


async def apply_tenant_update(db, tenant_id: str, payload: TenantUpdatePayload, user_id: Optional[str] = None, source: str = "settings") -> List[Dict[str, Any]]:
    """Saves the fields that were given and returns what changed. Raises ValueError with a message the owner can read."""
    now = datetime.now(timezone.utc)
    fields: Dict[str, Any] = {}
    if payload.business_name:
        fields["business_name"] = payload.business_name
    if payload.business_phone:
        fields["business_phone"] = payload.business_phone
    if payload.address:
        fields["address"] = payload.address
    if payload.currency:
        fields["currency"] = payload.currency
    if payload.timezone:
        try:
            ZoneInfo(payload.timezone)
        except ZoneInfoNotFoundError:
            raise ValueError(f"Unknown timezone: {payload.timezone}")
        fields["timezone"] = payload.timezone
    if payload.flat_delivery_fee is not None:
        fields["delivery_settings.flat_delivery_fee"] = payload.flat_delivery_fee
    if payload.avg_prep_time_minutes is not None:
        fields["delivery_settings.avg_prep_time_minutes"] = payload.avg_prep_time_minutes
    if payload.operating_hours is not None:
        if len(payload.operating_hours) != 7 or len({h.day for h in payload.operating_hours}) != 7:
            raise ValueError("operating_hours needs one entry for each day of the week.")
        fields["operating_hours"] = [h.model_dump() for h in payload.operating_hours]
    if payload.min_order_amount is not None:
        if payload.min_order_amount < 0:
            raise ValueError("The minimum order can't be negative.")
        fields["min_order_amount"] = payload.min_order_amount
    if payload.delivery_areas is not None:
        fields["delivery_areas"] = [a.strip() for a in payload.delivery_areas if a.strip()][:50]
    if payload.payment_methods is not None:
        if not payload.payment_methods:
            raise ValueError("Choose at least one payment method.")
        fields["payment_methods"] = payload.payment_methods
    if payload.order_types is not None:
        if not payload.order_types:
            raise ValueError("Choose at least one order type.")
        fields["order_types"] = payload.order_types
    if not fields:
        return []

    tenant = await db.tenants.find_one({"tenant_id": tenant_id}) or {}
    changes = [
        {"field": path, "before": _dig(tenant, path), "after": value}
        for path, value in fields.items()
        if _dig(tenant, path) != value
    ]
    if not changes:
        return []

    await db.tenants.update_one({"tenant_id": tenant_id}, {"$set": {**fields, "updated_at": now}})
    await log_changes(db, tenant_id, user_id, source, changes, now)
    return changes


async def apply_agent_settings(db, tenant_id: str, settings: AgentSettings, user_id: Optional[str] = None, source: str = "settings") -> List[Dict[str, Any]]:
    """Saves reply language, tone, greeting and escalation rules. Returns what changed."""
    now = datetime.now(timezone.utc)
    new_value = settings.model_dump()
    tenant = await db.tenants.find_one({"tenant_id": tenant_id}) or {}
    old_value = tenant.get("agent_settings") or {}
    changes = [
        {"field": f"agent_settings.{key}", "before": old_value.get(key), "after": value}
        for key, value in new_value.items()
        if old_value.get(key) != value
    ]
    if not changes:
        return []
    await db.tenants.update_one({"tenant_id": tenant_id}, {"$set": {"agent_settings": new_value, "updated_at": now}})
    await log_changes(db, tenant_id, user_id, source, changes, now)
    return changes
