"""
Broadcast campaigns: one approved template sent to a list of the business's customers.

A campaign is saved with one row per recipient, then sent in the background at a steady pace.
Delivery and read receipts come back through the webhook and update the rows and the totals.

Customers who reply STOP aren't sent campaigns again until they reply START.
"""

import asyncio
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, model_validator

from services.templates import find_template, send_template_message, sendable

logger = logging.getLogger(__name__)

CAMPAIGNS = "campaigns"
RECIPIENTS = "campaign_recipients"
OPT_OUTS = "marketing_opt_outs"

MAX_RECIPIENTS = 5000
MAX_LISTED_PHONES = 1000
SEND_GAP_SECONDS = 0.12          # about 8 a second, well inside Meta's limits for a new number
STALLED_AFTER = timedelta(minutes=3)

OPT_OUT_WORDS = {"stop", "unsubscribe", "stop promotions", "stop promotion"}
OPT_IN_WORDS = {"start", "subscribe"}

# Receipts only move a recipient forward. A failure can arrive at any point.
STATUS_RANK = {"queued": 0, "sent": 1, "delivered": 2, "read": 3}


class ParamSource(BaseModel):
    """Where one template value comes from: fixed text, or the customer's name."""
    kind: Literal["text", "customer_name"] = "text"
    value: str = Field("", max_length=1000)

    @model_validator(mode="after")
    def _filled(self) -> "ParamSource":
        if self.kind == "text" and not self.value.strip():
            raise ValueError("Fill in every template value.")
        return self


class Audience(BaseModel):
    kind: Literal["all", "ordered_within_days", "phones"] = "all"
    days: Optional[int] = Field(None, ge=1, le=365)
    phones: List[str] = Field(default_factory=list, max_length=MAX_LISTED_PHONES)

    @model_validator(mode="after")
    def _complete(self) -> "Audience":
        if self.kind == "ordered_within_days" and not self.days:
            raise ValueError("Say how many days back to look for orders.")
        if self.kind == "phones" and not self.phones:
            raise ValueError("Add at least one phone number.")
        return self


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    template_name: str
    language: str
    body_params: List[ParamSource] = Field(default_factory=list)
    header_params: List[ParamSource] = Field(default_factory=list)
    audience: Audience = Field(default_factory=Audience)


def normalize_phone(raw: str) -> Optional[str]:
    """WhatsApp ids are the full number in digits: 923001234567. None if it can't be one."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("00"):
        digits = digits[2:]
    return digits if 8 <= len(digits) <= 15 else None


def fill(sources: List[ParamSource], customer_name: str) -> List[str]:
    first = (customer_name or "").strip().split(" ")[0]
    return [(first or "there") if s.kind == "customer_name" else s.value for s in sources]


def is_opt_out(text: str) -> bool:
    return (text or "").strip().lower().rstrip(".!") in OPT_OUT_WORDS


def is_opt_in(text: str) -> bool:
    return (text or "").strip().lower().rstrip(".!") in OPT_IN_WORDS


async def opted_out_phones(db, tenant_id: str) -> set:
    rows = await db[OPT_OUTS].find({"tenant_id": tenant_id}, {"phone": 1}).to_list(length=100000)
    return {r["phone"] for r in rows if r.get("phone")}


async def handle_marketing_keywords(db, tenant: Dict[str, Any], phone: str, text: str) -> Optional[str]:
    """STOP and START from a customer. Returns the reply to send, or None if the message isn't one of them.
    START only counts from someone who opted out, so an ordinary "start" still reaches the agent."""
    tenant_id = tenant["tenant_id"]
    business = tenant.get("business_name") or "us"
    now = datetime.now(timezone.utc)
    if is_opt_out(text):
        await db[OPT_OUTS].update_one(
            {"tenant_id": tenant_id, "phone": phone},
            {"$set": {"tenant_id": tenant_id, "phone": phone, "at": now}},
            upsert=True,
        )
        return f"You won't get promotional messages from {business} anymore. Reply START to get them again."
    if is_opt_in(text) and await db[OPT_OUTS].find_one({"tenant_id": tenant_id, "phone": phone}):
        await db[OPT_OUTS].delete_one({"tenant_id": tenant_id, "phone": phone})
        return f"You'll get promotional messages from {business} again. Reply STOP any time to stop them."
    return None


async def resolve_audience(db, tenant_id: str, audience: Audience) -> Tuple[List[Dict[str, str]], int]:
    """(recipients, how many were left out because they opted out). Each recipient is {phone, name}."""
    names: Dict[str, str] = {}
    conversations = await db["conversations"].find(
        {"tenant_id": tenant_id}, {"customer_phone": 1, "customer_name": 1, "channel": 1}
    ).to_list(length=100000)
    for c in conversations:
        phone = normalize_phone(c.get("customer_phone") or "")
        if phone and (c.get("channel") or "whatsapp") == "whatsapp":
            names.setdefault(phone, c.get("customer_name") or "")

    if audience.kind == "all":
        wanted = list(names)
    elif audience.kind == "ordered_within_days":
        since = datetime.now(timezone.utc) - timedelta(days=audience.days or 30)
        orders = await db["orders"].find(
            {"tenant_id": tenant_id, "created_at": {"$gte": since}, "status": {"$nin": ["awaiting_customer", "cancelled", "expired"]}},
            {"customer_phone": 1, "customer_name": 1},
        ).to_list(length=100000)
        wanted = []
        for o in orders:
            phone = normalize_phone(o.get("customer_phone") or "")
            if phone and phone not in wanted:
                wanted.append(phone)
                if o.get("customer_name") and not names.get(phone):
                    names[phone] = o["customer_name"]
    else:
        wanted = []
        for raw in audience.phones:
            phone = normalize_phone(raw)
            if phone and phone not in wanted:
                wanted.append(phone)

    blocked = await opted_out_phones(db, tenant_id)
    kept = [p for p in wanted if p not in blocked]
    return [{"phone": p, "name": names.get(p, "")} for p in kept[:MAX_RECIPIENTS]], len(wanted) - len(kept)


def public_campaign(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: v for k, v in doc.items() if k not in ("_id", "tenant_id")}
    updated = doc.get("updated_at")
    if doc.get("status") == "sending" and isinstance(updated, datetime):
        updated = updated if updated.tzinfo else updated.replace(tzinfo=timezone.utc)
        out["stalled"] = datetime.now(timezone.utc) - updated > STALLED_AFTER
    else:
        out["stalled"] = False
    return out


async def create_campaign(db, tenant: Dict[str, Any], payload: CampaignCreate, user_id: Optional[str]) -> Dict[str, Any]:
    """Saves the campaign and its recipients. Raises ValueError with a reason the owner can read."""
    tenant_id = tenant["tenant_id"]
    doc = await find_template(db, tenant_id, payload.template_name, payload.language)
    ok, why = sendable(doc)
    if not ok:
        raise ValueError(why)
    if len(payload.body_params) != doc.get("body_variables", 0) or len(payload.header_params) != doc.get("header_variables", 0):
        raise ValueError(f"The template {doc['name']} needs {doc.get('body_variables', 0)} value(s). Fill in each one.")

    recipients, skipped = await resolve_audience(db, tenant_id, payload.audience)
    if not recipients:
        raise ValueError("No customers match this audience." + (" Everyone in it has opted out." if skipped else ""))

    now = datetime.now(timezone.utc)
    campaign_id = f"cmp_{uuid.uuid4().hex[:12]}"
    campaign = {
        "campaign_id": campaign_id,
        "tenant_id": tenant_id,
        "name": payload.name.strip(),
        "template_name": doc["name"],
        "language": doc["language"],
        "category": doc.get("category"),
        "body_params": [p.model_dump() for p in payload.body_params],
        "header_params": [p.model_dump() for p in payload.header_params],
        "audience": payload.audience.model_dump(),
        "status": "sending",
        "counts": {"total": len(recipients), "sent": 0, "delivered": 0, "read": 0, "failed": 0, "skipped_opted_out": skipped},
        "created_by": user_id,
        "created_at": now,
        "started_at": now,
        "updated_at": now,
        "finished_at": None,
        "error": None,
    }
    await db[CAMPAIGNS].insert_one(dict(campaign))
    await db[RECIPIENTS].insert_many([
        {"campaign_id": campaign_id, "tenant_id": tenant_id, "phone": r["phone"], "name": r["name"],
         "status": "queued", "wamid": None, "error": None, "updated_at": now}
        for r in recipients
    ])
    return campaign


async def run_campaign(db, tenant: Dict[str, Any], campaign_id: str, gap: float = SEND_GAP_SECONDS) -> str:
    """Sends to every recipient still queued. Safe to run again after a restart: sent rows are skipped.
    Returns the campaign's final status."""
    from services.alerts import raise_alert

    campaign = await db[CAMPAIGNS].find_one({"campaign_id": campaign_id, "tenant_id": tenant["tenant_id"]})
    if not campaign:
        return "missing"
    doc = await find_template(db, tenant["tenant_id"], campaign["template_name"], campaign["language"])
    ok, why = sendable(doc)
    if not ok:
        await _finish(db, campaign_id, "failed", why)
        return "failed"

    body_sources = [ParamSource(**p) for p in campaign.get("body_params") or []]
    header_sources = [ParamSource(**p) for p in campaign.get("header_params") or []]
    queued = await db[RECIPIENTS].find({"campaign_id": campaign_id, "status": "queued"}).to_list(length=MAX_RECIPIENTS)

    for row in queued:
        try:
            result, _ = await send_template_message(
                db, tenant, row["phone"], doc,
                fill(body_sources, row.get("name") or ""),
                fill(header_sources, row.get("name") or ""),
                sender="system",
            )
        except ValueError as e:
            await _finish(db, campaign_id, "failed", str(e))
            return "failed"
        now = datetime.now(timezone.utc)
        if not result.ok and result.auth_error:
            # Every send after this would fail the same way. Leave this row queued and stop.
            reason = "WhatsApp rejected the token. Reconnect WhatsApp in Settings, then resume the campaign."
            await _finish(db, campaign_id, "paused", reason)
            await raise_alert(db, tenant["tenant_id"], kind="campaign_paused", title=f"Campaign {campaign['name']} stopped",
                              detail=reason, severity="critical", ref={"campaign_id": campaign_id})
            return "paused"
        if result.ok:
            await db[RECIPIENTS].update_one(
                {"campaign_id": campaign_id, "phone": row["phone"]},
                {"$set": {"status": "sent", "wamid": result.message_id, "updated_at": now}},
            )
            await db[CAMPAIGNS].update_one({"campaign_id": campaign_id}, {"$inc": {"counts.sent": 1}, "$set": {"updated_at": now}})
        else:
            await db[RECIPIENTS].update_one(
                {"campaign_id": campaign_id, "phone": row["phone"]},
                {"$set": {"status": "failed", "error": result.error_message, "updated_at": now}},
            )
            await db[CAMPAIGNS].update_one({"campaign_id": campaign_id}, {"$inc": {"counts.failed": 1}, "$set": {"updated_at": now}})
        if gap:
            await asyncio.sleep(gap)

    await _finish(db, campaign_id, "done", None)
    return "done"


async def _finish(db, campaign_id: str, status: str, error: Optional[str]) -> None:
    now = datetime.now(timezone.utc)
    await db[CAMPAIGNS].update_one(
        {"campaign_id": campaign_id},
        {"$set": {"status": status, "error": error, "updated_at": now, "finished_at": now if status in ("done", "failed") else None}},
    )


def start_campaign(db, tenant: Dict[str, Any], campaign_id: str) -> None:
    """Runs the campaign in the background. Errors are logged and recorded on the campaign, never raised."""
    async def runner():
        try:
            await run_campaign(db, tenant, campaign_id)
        except Exception as e:
            logger.exception(f"Campaign {campaign_id} stopped: {e}")
            await _finish(db, campaign_id, "paused", "Sending stopped unexpectedly. Resume the campaign to continue.")

    asyncio.create_task(runner())


async def record_receipt(db, wamid: Optional[str], status: Optional[str], error: Optional[Dict[str, Any]] = None) -> bool:
    """A delivery receipt for a message a campaign sent. Updates the recipient and the campaign's totals.
    Returns whether the message belonged to a campaign."""
    if not wamid or status not in ("sent", "delivered", "read", "failed"):
        return False
    row = await db[RECIPIENTS].find_one({"wamid": wamid})
    if not row:
        return False
    old = row.get("status") or "sent"
    now = datetime.now(timezone.utc)
    inc: Dict[str, int] = {}
    fields: Dict[str, Any] = {"updated_at": now}
    if status == "failed":
        if old == "failed":
            return True
        fields["status"] = "failed"
        fields["error"] = (error or {}).get("title") or (error or {}).get("message") or "WhatsApp couldn't deliver it."
        inc["counts.failed"] = 1
        if old in ("delivered", "read"):
            inc["counts.delivered"] = -1
        if old == "read":
            inc["counts.read"] = -1
    else:
        if old == "failed" or STATUS_RANK.get(status, 0) <= STATUS_RANK.get(old, 0):
            return True
        fields["status"] = status
        if STATUS_RANK[status] >= STATUS_RANK["delivered"] > STATUS_RANK.get(old, 0):
            inc["counts.delivered"] = 1
        if status == "read":
            inc["counts.read"] = 1
    await db[RECIPIENTS].update_one({"_id": row["_id"]}, {"$set": fields})
    update: Dict[str, Any] = {"$set": {"updated_at": now}}
    if inc:
        update["$inc"] = inc
    await db[CAMPAIGNS].update_one({"campaign_id": row["campaign_id"]}, update)
    return True


async def ensure_campaign_indexes(db) -> None:
    await db[CAMPAIGNS].create_index([("tenant_id", 1), ("created_at", -1)], name="tenant_campaigns_recent")
    await db[RECIPIENTS].create_index([("campaign_id", 1), ("status", 1)], name="campaign_recipients_by_status")
    await db[RECIPIENTS].create_index("wamid", sparse=True, name="campaign_recipients_by_wamid")
    await db[OPT_OUTS].create_index([("tenant_id", 1), ("phone", 1)], unique=True, name="uniq_opt_out")
