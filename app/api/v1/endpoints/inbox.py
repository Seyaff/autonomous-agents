import logging
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.database import get_database
from services.channels import channel_of, send_text_to
from services.alerts import raise_alert
from middlewares.auth_middleware import require_owner
from repositories.inbox_repo import inbox_repo
from services.message_service import message_service
from services.conversation_state import broadcast_conversation_updated
from schemas.inbox import (
    SendMessageRequest,
    SendTemplateRequest,
    UpdateConversationRequest,
)
from services.order_service import customer_in_service_window
from services.templates import find_template, send_template_message

logger = logging.getLogger(__name__)

inbox_router = APIRouter(prefix="/inbox", tags=["Inbox"])

GroupName = Literal["needs_you", "owner_handling", "agent_handling", "resolved"]


async def _get_owned_conversation(conversation_id: str, tenant_id: str):
    conversation = await inbox_repo.get_conversation_raw(conversation_id, tenant_id)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


async def _change_handover(conversation_id: str, tenant_id: str, handled_by: str, user_id: str):
    conversation = await inbox_repo.set_handover(conversation_id, tenant_id, handled_by, user_id)
    await broadcast_conversation_updated(tenant_id, conversation)
    return conversation


@inbox_router.get("/conversations")
async def list_conversations(
    status_filter: Optional[str] = Query(None, alias="status"),
    group: Optional[GroupName] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    sort: str = Query("last_activity_at"),
    current_user: dict = Depends(require_owner),
):
    """Lists the active tenant's conversations, with the server-computed queue
    group on each item and counts per group for the queue headers."""
    tenant_id = current_user["active_tenant_id"]
    return await inbox_repo.list_conversations(
        tenant_id=tenant_id,
        status=status_filter,
        page=page,
        limit=limit,
        search=search,
        sort=sort,
        group=group,
    )


@inbox_router.get("/conversations/{conversation_id}")
async def get_conversation_detail(
    conversation_id: str,
    before_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    """Returns conversation metadata plus a page of its messages (oldest->newest),
    and whether a free-form reply can still be sent (Meta's 24-hour window)."""
    tenant_id = current_user["active_tenant_id"]
    conversation = await _get_owned_conversation(conversation_id, tenant_id)
    messages_page = await inbox_repo.get_messages(
        conversation_id=conversation_id, before_id=before_id, limit=limit
    )
    return {
        "conversation": conversation,
        "messages": messages_page["messages"],
        "has_more": messages_page["has_more"],
        "reply_window_open": await customer_in_service_window(db, tenant_id, conversation["customer_phone"]),
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
    await inbox_repo.update_conversation(
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        fields={"status": payload.status, "tags": payload.tags},
    )
    conversation = await inbox_repo.get_conversation_raw(conversation_id, tenant_id)
    await broadcast_conversation_updated(tenant_id, conversation)
    return {"status": "success", "conversation": conversation}


@inbox_router.post("/conversations/{conversation_id}/takeover")
async def take_over_conversation(
    conversation_id: str,
    current_user: dict = Depends(require_owner),
):
    """The owner takes the chat from the agent. The agent stops replying to
    this customer until the owner hands it back."""
    tenant_id = current_user["active_tenant_id"]
    await _get_owned_conversation(conversation_id, tenant_id)
    conversation = await _change_handover(conversation_id, tenant_id, "owner", current_user["user_id"])
    return {"status": "success", "conversation": conversation}


@inbox_router.post("/conversations/{conversation_id}/handback")
async def hand_back_conversation(
    conversation_id: str,
    current_user: dict = Depends(require_owner),
):
    """Hands the chat back to the agent. Also resolves any active escalation."""
    tenant_id = current_user["active_tenant_id"]
    await _get_owned_conversation(conversation_id, tenant_id)
    conversation = await _change_handover(conversation_id, tenant_id, "agent", current_user["user_id"])
    return {"status": "success", "conversation": conversation}


@inbox_router.post("/conversations/{conversation_id}/escalation/resolve")
async def resolve_escalation(
    conversation_id: str,
    current_user: dict = Depends(require_owner),
):
    """Clears the 'needs you' flag without changing who is handling the chat."""
    tenant_id = current_user["active_tenant_id"]
    await _get_owned_conversation(conversation_id, tenant_id)
    conversation = await inbox_repo.resolve_escalation(conversation_id, tenant_id, current_user["user_id"])
    await broadcast_conversation_updated(tenant_id, conversation)
    return {"status": "success", "conversation": conversation}


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
    """Lets the owner reply to a customer directly from the dashboard.

    Replying is taking over: if the agent was still handling the chat, it is
    switched to the owner first so the agent doesn't answer on top of them."""
    tenant_id = current_user["active_tenant_id"]
    conversation = await _get_owned_conversation(conversation_id, tenant_id)

    if not await customer_in_service_window(db, tenant_id, conversation["customer_phone"]):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "It's been more than 24 hours since this customer wrote. Instagram only allows a reply after they write again."
                if channel_of(conversation["customer_phone"]) == "instagram"
                else "It's been more than 24 hours since this customer wrote. WhatsApp only allows a template now."
            ),
        )

    if conversation.get("handled_by") != "owner":
        await _change_handover(conversation_id, tenant_id, "owner", current_user["user_id"])

    tenant = await db["tenants"].find_one({"tenant_id": tenant_id})

    message = await message_service.persist_outbound(
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        content=payload.content,
        message_type=payload.type,
        sender="human",
    )

    result = await send_text_to(tenant, conversation["customer_phone"], payload.content, db)
    sent = result.ok

    if message:
        await message_service.update_outbound_status(
            message_id=message.message_id,
            wamid=result.message_id or "",
            status="sent" if sent else "failed",
        )
    if not sent:
        await raise_alert(
            db,
            tenant_id,
            kind="owner_message_not_sent",
            title="Your reply wasn't delivered",
            detail=f"{conversation['customer_phone']}: {result.error_message or 'The message was not accepted.'}",
            severity="critical" if result.auth_error else "warning",
            ref={"conversation_id": conversation_id},
        )

    return {"status": "success" if sent else "failed", "message": message}


@inbox_router.post("/conversations/{conversation_id}/template")
async def send_template_to_conversation(
    conversation_id: str,
    payload: SendTemplateRequest,
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    """Sends an approved template, the only way to reach a customer more than 24 hours
    after they last wrote. Like a reply, it takes the chat over from the agent."""
    tenant_id = current_user["active_tenant_id"]
    conversation = await _get_owned_conversation(conversation_id, tenant_id)
    if channel_of(conversation["customer_phone"]) != "whatsapp":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Templates are a WhatsApp feature. Instagram customers can't get one.")
    tenant = await db["tenants"].find_one({"tenant_id": tenant_id})
    doc = await find_template(db, tenant_id, payload.name, payload.language)

    try:
        result, message = await send_template_message(
            db, tenant, conversation["customer_phone"], doc, payload.body_params, payload.header_params, sender="human"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if conversation.get("handled_by") != "owner":
        await _change_handover(conversation_id, tenant_id, "owner", current_user["user_id"])
    if not result.ok:
        await raise_alert(
            db,
            tenant_id,
            kind="owner_message_not_sent",
            title="Your template wasn't delivered",
            detail=f"{conversation['customer_phone']}: {result.error_message or 'WhatsApp did not accept it.'}",
            severity="critical" if result.auth_error else "warning",
            ref={"conversation_id": conversation_id},
        )
    return {"status": "success" if result.ok else "failed", "message": message, "error": None if result.ok else result.error_message}
