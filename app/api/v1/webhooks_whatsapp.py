import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, Query, Response, status
from sqlalchemy import select
from app.config import settings
from app.core.database import AsyncSessionLocal
from app.models.tenant import Tenant
from app.services.whatsapp_service import whatsapp_service
from app.services.audio_service import audio_service
from app.services.telemetry_service import telemetry_service
from app.agents.tenant.customer_support.graph import run_customer_support_graph
from app.agents.tenant.inventory.graph import process_owner_inventory_message

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/whatsapp", tags=["WhatsApp Webhook"])
alias_router = APIRouter(prefix="/whatsapp/webhook", tags=["WhatsApp Webhook"])

@router.get("")
@alias_router.get("")
async def verify_meta_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token")
):
    """Meta Webhook handshake verification endpoint."""
    if hub_mode == "subscribe" and hub_verify_token == settings.META_WEBHOOK_VERIFY_TOKEN:
        logger.info("Meta webhook verification successful.")
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Verification token mismatch", status_code=status.HTTP_403_FORBIDDEN)

@router.post("")
@alias_router.post("")
async def receive_meta_webhook(request: Request):
    """Handle inbound messages from WhatsApp Cloud API."""
    try:
        body = await request.json()
    except Exception:
        return Response(content="Invalid JSON", status_code=status.HTTP_400_BAD_REQUEST)

    # Check if this is an inbound message event
    entry = body.get("entry", [])
    if not entry:
        return {"status": "ignored_no_entry"}

    changes = entry[0].get("changes", [])
    if not changes:
        return {"status": "ignored_no_changes"}

    value = changes[0].get("value", {})
    metadata = value.get("metadata", {})
    phone_number_id = metadata.get("phone_number_id")
    messages = value.get("messages", [])

    if not messages:
        # Message status update (sent, delivered, read)
        return {"status": "status_update_acknowledged"}

    msg = messages[0]
    sender_phone = msg.get("from")
    msg_type = msg.get("type")

    # Start turn observability trace
    trace_ctx = telemetry_service.start_trace(
        customer_phone=sender_phone,
        turn_type="audio" if msg_type in ["audio", "voice"] else "text"
    )

    # Extract message content (Text, Voice/Audio, Interactive Buttons, Documents/Images)
    user_text = ""
    document_bytes = None

    if msg_type == "text":
        user_text = msg.get("text", {}).get("body", "")
    elif msg_type in ["audio", "voice"]:
        # Handle WhatsApp Voice Notes (Opus / OGG)
        audio_info = msg.get("audio", {}) or msg.get("voice", {})
        media_id = audio_info.get("id")
        mime_type = audio_info.get("mime_type", "audio/ogg")
        if media_id:
            token = settings.META_ACCESS_TOKEN
            trace_ctx.start_span("audio_download")
            audio_bytes = await whatsapp_service.download_media_bytes(media_id, token)
            trace_ctx.end_span("audio_download")

            if audio_bytes:
                trace_ctx.start_span("audio_transcription")
                raw_transcript, normalized_transcript = await audio_service.transcribe_voice_note(
                    audio_bytes=audio_bytes,
                    filename="voice_note.ogg",
                    mime_type=mime_type
                )
                trace_ctx.end_span("audio_transcription")
                user_text = normalized_transcript or raw_transcript
                logger.info(f"Voice note transcribed: raw='{raw_transcript}' -> normalized='{normalized_transcript}'")
    elif msg_type == "interactive":
        interactive = msg.get("interactive", {})
        if interactive.get("type") == "button_reply":
            user_text = interactive.get("button_reply", {}).get("title", "")
        elif interactive.get("type") == "list_reply":
            user_text = interactive.get("list_reply", {}).get("title", "")
    elif msg_type == "document":
        doc = msg.get("document", {})
        media_id = doc.get("id")
        filename = doc.get("filename", "menu.pdf")
        user_text = doc.get("caption") or f"Uploaded document: {filename}"
        if media_id:
            token = settings.META_ACCESS_TOKEN
            document_bytes = await whatsapp_service.download_media_bytes(media_id, token)
    elif msg_type == "image":
        img = msg.get("image", {})
        media_id = img.get("id")
        user_text = img.get("caption") or "Uploaded menu image"
        if media_id:
            token = settings.META_ACCESS_TOKEN
            document_bytes = await whatsapp_service.download_media_bytes(media_id, token)

    # Look up Tenant associated with this phone_number_id
    trace_ctx.start_span("db_tenant_lookup")
    async with AsyncSessionLocal() as db:
        stmt = (
            select(Tenant)
            .where(Tenant.phone_number_id == phone_number_id)
            .order_by(Tenant.is_active.desc(), Tenant.updated_at.desc())
        )
        res = await db.execute(stmt)
        tenant = res.scalars().first()

        # Fallback to first active tenant for testing/local development
        if not tenant:
            fallback_res = await db.execute(
                select(Tenant).where(Tenant.is_active == True).order_by(Tenant.updated_at.desc())
            )
            tenant = fallback_res.scalars().first()
    trace_ctx.end_span("db_tenant_lookup")

    if not tenant:
        logger.warning(f"No tenant found for phone_number_id: {phone_number_id}")
        trace_ctx.set_error("no_tenant", f"No tenant found for phone_number_id: {phone_number_id}")
        trace_ctx.finish()
        return {"status": "no_tenant_configured"}

    tenant_id = str(tenant.id)
    trace_ctx.trace.tenant_id = tenant_id

    # Route message based on sender identity
    reply_text = ""
    lower_text = user_text.lower().strip()
    is_owner = bool(tenant.owner_whatsapp_number and sender_phone.replace("+", "") == tenant.owner_whatsapp_number.replace("+", ""))
    
    # Check if this is an owner inventory command or uploaded menu document
    owner_keywords = ["inventory", "out of", "sold out", "ran out of", "back in stock", "restocked", "86", "/owner", "owner"]
    is_owner_inventory_cmd = is_owner and (any(kw in lower_text for kw in owner_keywords) or document_bytes is not None)

    if is_owner_inventory_cmd:
        # 1. Explicit Owner message or Document Ingestion -> Inventory Agent
        reply_text = await process_owner_inventory_message(
            tenant_id=tenant_id,
            owner_phone=sender_phone,
            message_text=user_text,
            document_bytes=document_bytes
        )
    elif settings.FOUNDER_PHONE_NUMBER and sender_phone.replace("+", "") == settings.FOUNDER_PHONE_NUMBER.replace("+", "") and lower_text.startswith("/founder"):
        # 2. Explicit Founder command -> Business Ops Agent
        reply_text = "👋 Hello Founder! Business Ops Agent reporting: All systems operational."
    else:
        # 3. Customer message (or Owner acting as a customer exploring the menu/ordering)
        trace_ctx.start_span("llm_generation")
        reply_text = await run_customer_support_graph(
            tenant_id=tenant_id,
            sender_phone=sender_phone,
            user_message=user_text
        )
        trace_ctx.end_span("llm_generation")

    trace_ctx.set_inputs_outputs(input_text=user_text, output_text=reply_text)

    # Dispatch reply back over WhatsApp
    if reply_text:
        trace_ctx.start_span("meta_api_send")
        # If the reply mentions order review / subtotal, send 1-click confirmation buttons!
        if "confirm order" in lower_text or "checkout" in lower_text:
            await whatsapp_service.send_text_message(
                to_phone=sender_phone,
                text=reply_text,
                phone_number_id=phone_number_id or tenant.phone_number_id,
                access_token=settings.META_ACCESS_TOKEN or tenant.meta_access_token
            )
        elif any(k in reply_text.lower() for k in ["cart total", "current cart", "order confirmed"]):
            await whatsapp_service.send_interactive_buttons(
                to_phone=sender_phone,
                body_text=reply_text,
                buttons=[
                    {"id": "btn_confirm", "title": "✅ Confirm Order"},
                    {"id": "btn_menu", "title": "🍽️ View Menu"}
                ],
                phone_number_id=phone_number_id or tenant.phone_number_id,
                access_token=settings.META_ACCESS_TOKEN or tenant.meta_access_token
            )
        else:
            await whatsapp_service.send_text_message(
                to_phone=sender_phone,
                text=reply_text,
                phone_number_id=phone_number_id or tenant.phone_number_id,
                access_token=settings.META_ACCESS_TOKEN or tenant.meta_access_token
            )
        trace_ctx.end_span("meta_api_send")

    trace_ctx.finish()
    return {"status": "success", "reply": reply_text, "trace_id": trace_ctx.trace.trace_id}
