from datetime import datetime, timezone
from typing import Any, Dict, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.database import get_database
from memory.customer_card import COUNTED_STATUSES, build_customer_card
from memory.facts import FACTS
from middlewares.auth_middleware import require_owner

customer_router = APIRouter(prefix="/customers", tags=["Customers"])


@customer_router.get("")
async def list_customers(
    search: Optional[str] = Query(None, description="Matches name or phone"),
    min_orders: Optional[int] = Query(None, ge=0),
    last_order_before: Optional[datetime] = None,
    last_order_after: Optional[datetime] = None,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    """Customers for the active restaurant, built from their orders. Filters
    are the segments the marketing agent and one-click campaigns will use."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant linked to your account.")

    pipeline: list = [
        {"$match": {"tenant_id": tenant_id}},
        {"$sort": {"created_at": -1}},
        {"$group": {
            "_id": "$customer_phone",
            "name": {"$first": "$customer_name"},
            "last_order_at": {"$first": "$created_at"},
            "total_orders": {"$sum": 1},
            "total_spent": {"$sum": {"$cond": [{"$in": ["$status", COUNTED_STATUSES]}, "$total_amount", 0]}},
            "currency": {"$first": "$currency"},
        }},
    ]

    match: Dict[str, Any] = {}
    if search:
        match["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"_id": {"$regex": search, "$options": "i"}},
        ]
    if min_orders is not None:
        match["total_orders"] = {"$gte": min_orders}
    if last_order_before:
        match.setdefault("last_order_at", {})["$lt"] = last_order_before
    if last_order_after:
        match.setdefault("last_order_at", {})["$gte"] = last_order_after
    if match:
        pipeline.append({"$match": match})

    pipeline.append({"$sort": {"last_order_at": -1}})
    pipeline.append({"$facet": {
        "total": [{"$count": "n"}],
        "page": [{"$skip": skip}, {"$limit": limit}],
    }})

    result = await (await db["orders"].aggregate(pipeline)).to_list(length=1)
    facet = result[0] if result else {"total": [], "page": []}

    customers = [
        {
            "customer_phone": row["_id"],
            "name": row.get("name"),
            "total_orders": row["total_orders"],
            "total_spent": round(row["total_spent"], 2),
            "currency": row.get("currency"),
            "last_order_at": row.get("last_order_at"),
        }
        for row in facet["page"]
    ]
    total = facet["total"][0]["n"] if facet["total"] else 0
    return {"total": total, "customers": customers}


@customer_router.get("/{customer_phone}")
async def get_customer(
    customer_phone: str,
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    """What the agent knows about one customer: stats, favourites, durable facts,
    and their five most recent orders."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant linked to your account.")

    card = await build_customer_card(db, tenant_id, customer_phone)
    if card["total_orders"] == 0 and not card["facts"] and not card["name"]:
        raise HTTPException(status_code=404, detail="Customer not found")

    recent = await db["orders"].find(
        {"tenant_id": tenant_id, "customer_phone": customer_phone},
        {"_id": 0, "order_id": 1, "status": 1, "total_amount": 1, "currency": 1, "created_at": 1, "items": 1},
    ).sort("created_at", -1).limit(5).to_list(length=5)

    return {"customer": card, "recent_orders": recent}


class FactEdit(BaseModel):
    value: str = Field(..., min_length=1, max_length=200)


def _fact_id(fact_id: str) -> ObjectId:
    try:
        return ObjectId(fact_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=404, detail="That fact isn't on file.")


@customer_router.get("/{customer_phone}/facts")
async def list_customer_facts(
    customer_phone: str,
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    """Everything the agent remembers about this customer, so the owner can check and correct it."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant found.")
    rows = await db[FACTS].find(
        {"tenant_id": tenant_id, "customer_phone": customer_phone, "active": True},
        {"kind": 1, "key": 1, "value": 1, "source": 1, "updated_at": 1},
    ).sort("updated_at", -1).to_list(length=100)
    return {"facts": [{"id": str(r.pop("_id")), **r} for r in rows]}


@customer_router.patch("/{customer_phone}/facts/{fact_id}")
async def correct_customer_fact(
    customer_phone: str,
    fact_id: str,
    payload: FactEdit,
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    """Corrects something the agent remembers. The owner's version is kept as the fact."""
    tenant_id = current_user.get("active_tenant_id")
    result = await db[FACTS].update_one(
        {"_id": _fact_id(fact_id), "tenant_id": tenant_id, "customer_phone": customer_phone, "active": True},
        {"$set": {"value": payload.value.strip(), "source": "owner", "updated_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="That fact isn't on file.")
    return {"id": fact_id, "value": payload.value.strip()}


@customer_router.delete("/{customer_phone}/facts/{fact_id}")
async def forget_customer_fact(
    customer_phone: str,
    fact_id: str,
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    """Removes something the agent remembers. The agent stops using it."""
    tenant_id = current_user.get("active_tenant_id")
    result = await db[FACTS].update_one(
        {"_id": _fact_id(fact_id), "tenant_id": tenant_id, "customer_phone": customer_phone, "active": True},
        {"$set": {"active": False, "source": "owner_removed", "updated_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="That fact isn't on file.")
    return {"status": "forgotten"}
