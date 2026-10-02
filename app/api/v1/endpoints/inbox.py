import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.database import get_database
from core.whatsapp_utils import resolve_tenant_whatsapp_credentials, send_whatsapp_message
from middlewares.auth_middleware import require_owner
from repositories.inbox_repo import inbox_repo
from services.message_service import message_service
from schemas.inbox import (
    SendMessageRequest,
    UpdateConversationRequest,
)

logger = logging.getLogger(__name__)

inbox_router = APIRouter(prefix="/inbox", tags=["Inbox"])


async def _get_owned_conversation(conversation_id: str, tenant_id: str):
    conversation = await inbox_repo.get_conversation(conversation_id)
    if not conversation or conversation.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


@inbox_router.get("/conversations")
async def list_conversations(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    sort: str = Query("last_activity_at"),
    current_user: dict = Depends(require_owner),
):
    """Lists the active tenant's conversations for the live inbox view."""
    tenant_id = current_user["active_tenant_id"]
    result = await inbox_repo.list_conversations(
        tenant_id=tenant_id,
        status=status_filter,
        page=page,
        limit=limit,
        search=search,
        sort=sort,
    )
    return result


@inbox_router.get("/conversations/{conversation_id}")
async def get_conversation_detail(
    conversation_id: str,
    before_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(require_owner),
):
    """Returns conversation metadata plus a page of its messages (oldest->newest)."""
    tenant_id = current_user["active_tenant_id"]
    conversation = await _get_owned_conversation(conversation_id, tenant_id)
    messages_page = await inbox_repo.get_messages(
        conversation_id=conversation_id, before_id=before_id, limit=limit
    )
    return {
        "conversation": conversation,
        "messages": messages_page["messages"],
        "has_more": messages_page["has_more"],
    }


@inbox_router.patch("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    payload: UpdateConversationRequest,
    current_user: dict = Depends(require_owner),
):
    """Updates conversation status (open/closed/archived) or tags."""
    tenant_id = current_user["active_tenant_id"]
    await _get_owned_conversation(conversation_id, tenant_id)
    updated = await inbox_repo.update_conversation(
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        fields={"status": payload.status, "tags": payload.tags},
    )
    return {"status": "success", "conversation": updated}


@inbox_router.post("/conversations/{conversation_id}/read")
async def mark_conversation_read(
    conversation_id: str,
    current_user: dict = Depends(require_owner),
):
    """Marks every unread customer message in the conversation as read."""
    tenant_id = current_user["active_tenant_id"]
    await _get_owned_conversation(conversation_id, tenant_id)
    count = await message_service.mark_conversation_read(conversation_id, tenant_id)
    return {"status": "success", "marked_read": count}


@inbox_router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    payload: SendMessageRequest,
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    """Lets the owner reply to a customer directly from the dashboard."""
    tenant_id = current_user["active_tenant_id"]
    conversation = await _get_owned_conversation(conversation_id, tenant_id)

    tenant = await db["tenants"].find_one({"tenant_id": tenant_id})
    token, phone_number_id = resolve_tenant_whatsapp_credentials(tenant)

    message = await message_service.persist_outbound(
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        content=payload.content,
        message_type=payload.type,
        sender="human",
    )

    sent = await send_whatsapp_message(
        to_phone=conversation.customer_phone,
        text=payload.content,
        token=token,
        phone_number_id=phone_number_id,
    )

    if message:
        await message_service.update_outbound_status(
            message_id=message.message_id,
            wamid="pending",
            status="sent" if sent else "failed",
        )

    return {"status": "success" if sent else "failed", "message": message}
