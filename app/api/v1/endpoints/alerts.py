from datetime import datetime, timezone

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.database import get_database
from middlewares.auth_middleware import require_owner
from services.alerts import ALERT_KINDS, serialize, whatsapp_kinds_for

alert_router = APIRouter(prefix="/alerts", tags=["Alerts"])


def _tenant(current_user: dict) -> str:
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant linked to your account.")
    return tenant_id


@alert_router.get("")
async def list_alerts(
    limit: int = Query(30, ge=1, le=100),
    unread_only: bool = False,
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    """Newest first. unread_count is for the header badge."""
    tenant_id = _tenant(current_user)
    query = {"tenant_id": tenant_id}
    if unread_only:
        query["read_at"] = None
    docs = await db["owner_alerts"].find(query).sort("created_at", -1).limit(limit).to_list(length=limit)
    unread = await db["owner_alerts"].count_documents({"tenant_id": tenant_id, "read_at": None})
    return {"alerts": [serialize(d) for d in docs], "unread_count": unread}


@alert_router.post("/read-all")
async def mark_all_read(
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    tenant_id = _tenant(current_user)
    res = await db["owner_alerts"].update_many(
        {"tenant_id": tenant_id, "read_at": None},
        {"$set": {"read_at": datetime.now(timezone.utc)}},
    )
    return {"status": "success", "marked": res.modified_count}


@alert_router.post("/{alert_id}/read")
async def mark_read(
    alert_id: str,
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    from bson import ObjectId
    from bson.errors import InvalidId

    tenant_id = _tenant(current_user)
    try:
        oid = ObjectId(alert_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Alert not found")
    res = await db["owner_alerts"].update_one(
        {"_id": oid, "tenant_id": tenant_id, "read_at": None},
        {"$set": {"read_at": datetime.now(timezone.utc)}},
    )
    return {"status": "success", "marked": res.modified_count}


class AlertPreferences(BaseModel):
    whatsapp_kinds: List[str]


@alert_router.get("/preferences")
async def get_alert_preferences(
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    """Which alerts the owner gets on WhatsApp. Everything else only shows in the dashboard."""
    tenant_id = _tenant(current_user)
    tenant = await db["tenants"].find_one({"tenant_id": tenant_id}, {"business_phone": 1, "alert_whatsapp_kinds": 1}) or {}
    chosen = set(whatsapp_kinds_for(tenant))
    return {
        "owner_phone": tenant.get("business_phone"),
        "kinds": [
            {"kind": kind, "label": info["label"], "description": info["description"], "whatsapp": kind in chosen}
            for kind, info in ALERT_KINDS.items()
        ],
    }


@alert_router.put("/preferences")
async def set_alert_preferences(
    payload: AlertPreferences,
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    tenant_id = _tenant(current_user)
    unknown = [k for k in payload.whatsapp_kinds if k not in ALERT_KINDS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown alert kinds: {', '.join(unknown)}")
    kinds = sorted(set(payload.whatsapp_kinds))
    await db["tenants"].update_one({"tenant_id": tenant_id}, {"$set": {"alert_whatsapp_kinds": kinds, "updated_at": datetime.now(timezone.utc)}})
    return {"whatsapp_kinds": kinds}
