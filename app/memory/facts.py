"""
Durable facts about a customer: preferences, dietary needs, addresses,
complaints, standing instructions.

Facts are never overwritten. When a value changes, the old fact is marked
inactive (with superseded_at) and a new one is written, so the history of
what we knew and when is kept. Every fact records where it came from.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

FACTS = "customer_facts"
FACT_KINDS = ("preference", "dietary", "allergy", "address", "complaint", "note", "service")
MIN_CONFIDENCE = 0.5


class FactChange(BaseModel):
    """One change proposed by the extractor. Validated before anything is stored."""

    action: Literal["set", "forget"] = "set"
    kind: str
    key: str = Field(min_length=1, max_length=60)
    value: str = Field(default="", max_length=300)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)

    @field_validator("kind")
    @classmethod
    def _known_kind(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in FACT_KINDS:
            raise ValueError(f"unknown fact kind: {v}")
        return v

    @field_validator("key")
    @classmethod
    def _slug(cls, v: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", v.strip().lower()).strip("_")[:60]

    @field_validator("value")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def list_active_facts(db, tenant_id: str, customer_phone: str, limit: int = 15) -> List[Dict[str, Any]]:
    cursor = db[FACTS].find(
        {"tenant_id": tenant_id, "customer_phone": customer_phone, "active": True},
        {"_id": 0, "kind": 1, "key": 1, "value": 1, "source": 1, "updated_at": 1},
    ).sort("updated_at", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def apply_fact_changes(
    db,
    tenant_id: str,
    customer_phone: str,
    changes: Iterable[FactChange],
    source: Dict[str, Any],
) -> int:
    """Writes validated changes. Returns how many facts were added or updated."""
    written = 0
    now = _now()
    for change in changes:
        match = {
            "tenant_id": tenant_id,
            "customer_phone": customer_phone,
            "kind": change.kind,
            "key": change.key,
            "active": True,
        }

        if change.action == "forget":
            res = await db[FACTS].update_many(
                match, {"$set": {"active": False, "superseded_at": now}}
            )
            written += res.modified_count
            continue

        if change.confidence < MIN_CONFIDENCE or not change.value:
            continue

        existing = await db[FACTS].find_one(match)
        if existing and existing.get("value") == change.value:
            # Same fact again: just refresh it.
            await db[FACTS].update_one({"_id": existing["_id"]}, {"$set": {"updated_at": now}})
            continue

        if existing:
            await db[FACTS].update_one(
                {"_id": existing["_id"]}, {"$set": {"active": False, "superseded_at": now}}
            )

        await db[FACTS].insert_one({
            "tenant_id": tenant_id,
            "customer_phone": customer_phone,
            "kind": change.kind,
            "key": change.key,
            "value": change.value,
            "confidence": change.confidence,
            "source": source,
            "active": True,
            "created_at": now,
            "updated_at": now,
            "superseded_at": None,
        })
        written += 1

    return written


async def ensure_fact_indexes(db) -> None:
    await db[FACTS].create_index(
        [("tenant_id", 1), ("customer_phone", 1), ("active", 1), ("updated_at", -1)],
        name="customer_active_facts",
    )
