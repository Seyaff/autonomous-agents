import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.database import get_database
from middlewares.auth_middleware import require_owner
from services.forms import (
    FORM_RESPONSES,
    FORMS,
    FormDraft,
    build_flow_json,
    delete_form,
    draft_of,
    preview_link,
    public_form,
    publish_form,
    save_form,
)

logger = logging.getLogger(__name__)

forms_router = APIRouter(prefix="/forms", tags=["WhatsApp forms"])


async def _tenant(db, current_user: dict) -> Dict[str, Any]:
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active business found.")
    tenant = await db.tenants.find_one({"tenant_id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=404, detail="Business record not found.")
    return tenant


async def _form(db, tenant_id: str, form_id: str) -> Dict[str, Any]:
    doc = await db[FORMS].find_one({"tenant_id": tenant_id, "form_id": form_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Form not found.")
    return doc


@forms_router.get("")
async def list_forms(db=Depends(get_database), current_user: dict = Depends(require_owner)):
    tenant = await _tenant(db, current_user)
    rows = await db[FORMS].find({"tenant_id": tenant["tenant_id"]}).sort("created_at", -1).to_list(length=100)
    return {
        "forms": [public_form(r) for r in rows],
        "whatsapp_connected": bool(tenant.get("whatsapp_business_id") and tenant.get("whatsapp_access_token")),
    }


@forms_router.post("", status_code=201)
async def create_form(draft: FormDraft, db=Depends(get_database), current_user: dict = Depends(require_owner)):
    """Saves a new form. It isn't sent to anyone until it's published."""
    tenant = await _tenant(db, current_user)
    return {"form": public_form(await save_form(db, tenant["tenant_id"], draft))}


@forms_router.get("/{form_id}")
async def get_form(form_id: str, db=Depends(get_database), current_user: dict = Depends(require_owner)):
    tenant = await _tenant(db, current_user)
    return {"form": public_form(await _form(db, tenant["tenant_id"], form_id))}


@forms_router.put("/{form_id}")
async def update_form(form_id: str, draft: FormDraft, db=Depends(get_database), current_user: dict = Depends(require_owner)):
    """Saves changes. A published form keeps working as it was until it's published again."""
    tenant = await _tenant(db, current_user)
    try:
        doc = await save_form(db, tenant["tenant_id"], draft, form_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"form": public_form(doc)}


@forms_router.post("/{form_id}/publish")
async def publish(form_id: str, db=Depends(get_database), current_user: dict = Depends(require_owner)):
    """Puts the form on the business's WhatsApp account, so the agent can send it."""
    tenant = await _tenant(db, current_user)
    try:
        doc = await publish_form(db, tenant, form_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"form": public_form(doc)}


@forms_router.get("/{form_id}/preview")
async def preview(form_id: str, db=Depends(get_database), current_user: dict = Depends(require_owner)):
    """A link to Meta's preview of the form, and the Flow JSON it's built from."""
    tenant = await _tenant(db, current_user)
    doc = await _form(db, tenant["tenant_id"], form_id)
    url: Optional[str] = None
    try:
        url = await preview_link(tenant, doc)
    except Exception as e:
        logger.warning(f"Form preview link failed for {form_id}: {e}")
    return {"preview_url": url, "flow_json": build_flow_json(draft_of(doc))}


@forms_router.delete("/{form_id}")
async def remove(form_id: str, db=Depends(get_database), current_user: dict = Depends(require_owner)):
    tenant = await _tenant(db, current_user)
    try:
        await delete_form(db, tenant, form_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "deleted"}


@forms_router.get("/{form_id}/responses")
async def responses(
    form_id: str,
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_database),
    current_user: dict = Depends(require_owner),
):
    """What customers sent back, newest first."""
    tenant = await _tenant(db, current_user)
    await _form(db, tenant["tenant_id"], form_id)
    rows = await db[FORM_RESPONSES].find(
        {"tenant_id": tenant["tenant_id"], "form_id": form_id}
    ).sort("received_at", -1).limit(limit).to_list(length=limit)
    for r in rows:
        r.pop("_id", None)
        r.pop("tenant_id", None)
        r.pop("raw", None)
    return {"responses": rows}
