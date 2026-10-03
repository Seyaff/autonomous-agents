from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from core.database import get_database
from middlewares.auth_middleware import require_owner
from services.alerts import serialize

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
