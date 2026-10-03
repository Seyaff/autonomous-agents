import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from fastapi import (
    APIRouter,
    Request,
    Query,
    Response,
    status,
    BackgroundTasks,
    Depends,
)
from pymongo.errors import DuplicateKeyError

from core.settings import settings
from core.database import get_database
from services.alerts import raise_alert
from core.whatsapp_utils import (
    download_whatsapp_media,
    send_text,
    send_whatsapp_message,
    resolve_tenant_whatsapp_credentials,
)
from services.pdf_ingestion import process_and_store_pdf_bytes
from agents.customer_support.agent import run_customer_support_turn
from services.billing import agent_allowed
from services.message_service import message_service
from services.conversation_state import conversation_blocks_agent, is_escalated

logger = logging.getLogger(__name__)

whatsapp_router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Webhook"])
alias_router = APIRouter(prefix="/whatsapp/webhook", tags=["WhatsApp Webhook"])


# ---------------------------------------------------------------------------
# Meta webhook handshake
# ---------------------------------------------------------------------------
@whatsapp_router.get("")
@whatsapp_router.get("/")
@alias_router.get("")
@alias_router.get("/")
async def verify_meta_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
):
    """Meta Webhook handshake verification endpoint."""
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("Meta webhook verification successful.")
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(
        content="Verification token mismatch",
        status_code=status.HTTP_403_FORBIDDEN,
    )


# ---------------------------------------------------------------------------
# Background handlers (run AFTER response is sent)
# ---------------------------------------------------------------------------
async def handle_inbound_pdf(
    media_id: str,
    filename: str,
    sender_phone: str,
    tenant_id: str,
    token: Optional[str] = None,
    phone_number_id: Optional[str] = None,
    request_id: str = "bg",
):
    """Download PDF, chunk, embed into tenant's Pinecone namespace, notify user."""
    try:
        await send_whatsapp_message(
            to_phone=sender_phone,
            text=f"📄 Processing '{filename}'... I am indexing your restaurant menu.",
            token=token,
            phone_number_id=phone_number_id,
        )

        file_bytes = await download_whatsapp_media(media_id, token=token)

        num_chunks = await process_and_store_pdf_bytes(
            file_bytes=file_bytes,
            filename=filename,
            tenant_id=tenant_id,
        )

        if num_chunks > 0:
            reply = (
                f"✅ Finished indexing '{filename}' ({num_chunks} chunks). "
                f"Customers can now query your dishes, deals, and prices!"
            )
        else:
            reply = (
                f"⚠️ Could not extract readable text from '{filename}'. "
                f"Please ensure it is not an image-only scan."
            )

    except Exception as e:
        logger.error(f"[{request_id}] Error executing PDF ingestion for tenant {tenant_id}: {e}")
        reply = "❌ An error occurred while processing your document."

    await send_whatsapp_message(
        to_phone=sender_phone,
        text=reply,
        token=token,
        phone_number_id=phone_number_id,
    )


PAUSED_NOTICE = "Abhi yeh restaurant messages ka jawab nahi de sakta. Thori dair baad dobara message karein."
PAUSED_NOTICE_EVERY = timedelta(hours=24)


async def _send_paused_notice(database, tenant_id: str, customer_phone: str, token, phone_id) -> None:
    """Tells a customer, at most once a day, that the restaurant isn't taking messages right now."""
    now = datetime.now(timezone.utc)
    conversation = await database["conversations"].find_one(
        {"tenant_id": tenant_id, "customer_phone": customer_phone}, {"paused_notice_at": 1}
    )
    last = (conversation or {}).get("paused_notice_at")
    if last and now - (last if last.tzinfo else last.replace(tzinfo=timezone.utc)) < PAUSED_NOTICE_EVERY:
        return
    await send_text(to_phone=customer_phone, text=PAUSED_NOTICE, token=token, phone_number_id=phone_id)
    await database["conversations"].update_one(
        {"tenant_id": tenant_id, "customer_phone": customer_phone}, {"$set": {"paused_notice_at": now}}
    )


VOICE_FALLBACK = "Voice note samajh nahi aayi. Please text mein likh dein."


async def handle_voice_turn(
    database,
    tenant: Dict[str, Any],
    tenant_id: str,
    sender_phone: str,
    media_id: str,
    tenant_token: Optional[str],
    tenant_phone_id: Optional[str],
    request_id: str = "bg",
    customer_name: str = "",
):
    """Background task for a voice note: download, transcribe, then handle as text."""
    from services.voice_transcription import TranscriptionError, transcribe_urdu_audio

    try:
        audio = await download_whatsapp_media(media_id, token=tenant_token)
        transcript = await transcribe_urdu_audio(audio)
    except (ValueError, TranscriptionError) as e:
        logger.warning(f"[{request_id}] Voice note from [{sender_phone}] not transcribed: {e}")
        transcript = ""
    except Exception as e:
        logger.exception(f"[{request_id}] Voice note from [{sender_phone}] failed: {e}")
        transcript = ""

    if not transcript:
        await send_text(to_phone=sender_phone, text=VOICE_FALLBACK, token=tenant_token, phone_number_id=tenant_phone_id)
        return

    logger.info(f"[{request_id}] Voice note from [{sender_phone}] transcribed: {transcript[:120]}")
    await handle_text_turn(
        database=database,
        tenant=tenant,
        tenant_id=tenant_id,
        sender_phone=sender_phone,
        user_payload=f"[voice note] {transcript}",
        tenant_token=tenant_token,
        tenant_phone_id=tenant_phone_id,
        request_id=request_id,
        customer_name=customer_name,
    )


async def handle_text_turn(
    database,
    tenant: Dict[str, Any],
    tenant_id: str,
    sender_phone: str,
    user_payload: str,
    tenant_token: Optional[str],
    tenant_phone_id: Optional[str],
    request_id: str = "bg",
    customer_name: str = "",
):
    """Background task for an inbound text message."""
    try:
        logger.info(
            f"[{request_id}] Incoming message from [{sender_phone}] for tenant [{tenant_id}]: {user_payload}"
        )

        # Persist inbound message
        await message_service.persist_inbound(
            tenant_id=tenant_id,
            sender_phone=sender_phone,
            content=user_payload,
            message_type="text",
            wamid=request_id,  # using request_id as fallback, actual wamid would come from webhook
            customer_name=customer_name,
        )

        # The inbound message is already saved. Don't let the agent answer if
        # the owner has taken the chat, it's waiting on the owner after an
        # escalation, or the restaurant has paused the agent globally.
        conversation = await database["conversations"].find_one(
            {"tenant_id": tenant_id, "customer_phone": sender_phone}
        )
        if conversation_blocks_agent(conversation, tenant):
            logger.info(
                f"[{request_id}] Agent skipped for [{sender_phone}] — "
                f"handled_by={(conversation or {}).get('handled_by', 'agent')}, "
                f"escalated={is_escalated(conversation or {})}, "
                f"agent_enabled={tenant.get('agent_enabled', True)}"
            )
            return

        # Billing: a paused or canceled restaurant, or a trial that has ended or hit its cap,
        # doesn't get agent replies. The message is still saved to the inbox.
        allowed, reason = await agent_allowed(database, tenant)
        if not allowed:
            logger.info(f"[{request_id}] Agent skipped for [{sender_phone}] — {reason}")
            if reason == "subscription paused":
                await _send_paused_notice(database, tenant_id, sender_phone, tenant_token, tenant_phone_id)
            return

        reply_text = await run_customer_support_turn(
            db=database,
            tenant=tenant,
            customer_phone=sender_phone,
            user_message=user_payload,
            inbound_wamid=request_id,
        )

        if reply_text:
            logger.info(
                f"[{request_id}] Agent reply to [{sender_phone}] for tenant [{tenant_id}]: {reply_text}"
            )
            
            # Persist outbound message (optimistic)
            # Get conversation_id from thread_id format
            conversation_id = f"conv_{tenant_id}_{sender_phone}"
            message = await message_service.persist_outbound(
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                content=reply_text,
                message_type="text",
                sender="agent",
            )
            
            # Send via WhatsApp. Record what actually happened, and tell the owner if it didn't go.
            result = await send_text(
                to_phone=sender_phone,
                text=reply_text,
                token=tenant_token,
                phone_number_id=tenant_phone_id,
            )
            if message:
                await message_service.update_outbound_status(
                    message_id=message.message_id,
                    wamid="pending",  # placeholder, actual wamid from Meta callback
                    status="sent" if result.ok else "failed",
                )
            if not result.ok:
                await _report_send_failure(database, tenant_id, sender_phone, result, "reply")
    except Exception as e:
        logger.exception(f"[{request_id}] Background text turn failed for {sender_phone}: {e}")
        await raise_alert(
            database,
            tenant_id,
            kind="message_not_handled",
            title=f"A message from {sender_phone} was not handled",
            detail=f"Something went wrong while answering. Check the conversation in your inbox. ({type(e).__name__})",
            severity="critical",
            ref={"customer_phone": sender_phone},
        )


async def _report_send_failure(database, tenant_id: str, sender_phone: str, result, what: str) -> None:
    """A WhatsApp send failed. If the token is the problem, the restaurant is marked disconnected too."""
    if result.auth_error:
        await database["tenants"].update_one(
            {"tenant_id": tenant_id},
            {"$set": {
                "whatsapp_status": "error",
                "whatsapp_last_error": result.error_message or "WhatsApp rejected the token",
                "whatsapp_checked_at": datetime.now(timezone.utc),
            }},
        )
        await raise_alert(
            database,
            tenant_id,
            kind="whatsapp_disconnected",
            title="WhatsApp is disconnected",
            detail="Customers aren't getting replies. Reconnect WhatsApp in Settings.",
            severity="critical",
        )
    else:
        await raise_alert(
            database,
            tenant_id,
            kind=f"{what}_not_sent",
            title=f"A {what} to {sender_phone} wasn't delivered",
            detail=result.error_message or "WhatsApp did not accept the message.",
            severity="warning",
            ref={"customer_phone": sender_phone},
        )


async def handle_button_reply(
    database,
    tenant: Dict[str, Any],
    tenant_id: str,
    sender_phone: str,
    button_id: str,
    button_title: str,
    wamid: Optional[str],
    request_id: str = "bg",
):
    """A customer tapped a button (Confirm or Cancel on an order summary)."""
    from services.order_confirmation import handle_tap

    try:
        await message_service.persist_inbound(
            tenant_id=tenant_id,
            sender_phone=sender_phone,
            content=f"[{button_title}]",
            message_type="text",
            wamid=wamid or request_id,
            customer_name="",
        )
        outcome = await handle_tap(database, tenant, sender_phone, button_id)
        logger.info(f"[{request_id}] Button '{button_title}' from [{sender_phone}]: {outcome}")
    except Exception as e:
        logger.exception(f"[{request_id}] Button handling failed for {sender_phone}: {e}")
        await raise_alert(
            database,
            tenant_id,
            kind="order_confirmation_failed",
            title=f"A customer's order answer ({button_title}) wasn't handled",
            detail=f"Check the order for {sender_phone} in the orders page. ({type(e).__name__})",
            severity="critical",
            ref={"customer_phone": sender_phone},
        )


# ---------------------------------------------------------------------------
# Main webhook receiver
# ---------------------------------------------------------------------------
@whatsapp_router.post("")
@whatsapp_router.post("/")
@alias_router.post("")
@alias_router.post("/")
async def receive_meta_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    database=Depends(get_database),
):
    """
    Receive inbound WhatsApp webhooks.

    Design:
      - Parse → resolve tenant → dedup → enqueue → return 200 immediately.
      - All slow work (LLM, media download) runs in BackgroundTasks.
      - Dedup on `message.id` (wamid) via a unique Mongo index so Meta's
        retries (which fire when we're slow) are silently dropped.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    # ---- 1. Parse ----
    try:
        body = await request.json()
    except Exception:
        return Response(content="Invalid JSON", status_code=status.HTTP_400_BAD_REQUEST)

    try:
        entry = body.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        metadata = value.get("metadata", {})
        messages = value.get("messages", [])
        contacts = value.get("contacts", [])

        inbound_phone_id = metadata.get("phone_number_id")
        display_number = metadata.get("display_phone_number")
        customer_name = (contacts[0].get("profile", {}).get("name", "") if contacts else "")
    except (IndexError, AttributeError, KeyError) as e:
        logger.error(f"[{request_id}] Error parsing webhook payload: {e}")
        return {"status": "success"}  # always ACK Meta

    # ---- 2. Resolve tenant ----
    # Route only by the number the message was sent to. Never guess a restaurant:
    # answering as the wrong one would put a customer's message in another owner's inbox.
    tenant = None
    if inbound_phone_id:
        tenant = await database["tenants"].find_one({"phone_number_id": inbound_phone_id})
    if not tenant:
        logger.warning(
            f"[{request_id}] No restaurant is connected to phone_number_id={inbound_phone_id} "
            f"(display_number={display_number}). Message not answered."
        )
        return {"status": "no_tenant_matched"}

    if not tenant:
        logger.warning(f"[{request_id}] No tenant configured in database for inbound WhatsApp message.")
        return {"status": "no_tenant_configured"}

    tenant_id = tenant.get("tenant_id", "default_tenant")
    tenant_token, tenant_phone_id = resolve_tenant_whatsapp_credentials(tenant)

    # Status updates (delivered/read receipts) have no "messages" key — ignore.
    if not messages:
        return {"status": "success"}

    msg = messages[0]
    sender_phone = msg.get("from")
    msg_type = msg.get("type")
    message_id = msg.get("id")  # wamid

    # ---- LOG: every inbound webhook hit ----
    logger.info(
        f"[{request_id}] [webhook] received msg_id={message_id} from={sender_phone} "
        f"type={msg_type} tenant={tenant_id}"
    )

    # ---- 3. DEDUP GATE (atomic — must run before we do any work) ----
    if message_id:
        try:
            await database["processed_messages"].insert_one(
                {
                    "message_id": message_id,
                    "tenant_id": tenant_id,
                    "sender_phone": sender_phone,
                    "msg_type": msg_type,
                    "received_at": datetime.utcnow(),
                }
            )
        except DuplicateKeyError:
            logger.warning(
                f"[{request_id}] [dedup] Dropped duplicate webhook: msg_id={message_id} "
                f"from={sender_phone} tenant={tenant_id}"
            )
            return {"status": "duplicate_ignored"}

    # ---- 4. Dispatch (never block the ACK) ----
    if msg_type == "document":
        doc_meta = msg.get("document", {})
        mime_type = doc_meta.get("mime_type", "")
        media_id = doc_meta.get("id")
        filename = doc_meta.get("filename", "document.pdf")

        if "pdf" in mime_type and media_id and sender_phone:
            background_tasks.add_task(
                handle_inbound_pdf,
                media_id=media_id,
                filename=filename,
                sender_phone=sender_phone,
                tenant_id=tenant_id,
                token=tenant_token,
                phone_number_id=tenant_phone_id,
                request_id=request_id,
            )

    elif msg_type == "text":
        user_payload = msg.get("text", {}).get("body", "")
        if user_payload and sender_phone:
            background_tasks.add_task(
                handle_text_turn,
                database=database,
                tenant=tenant,
                tenant_id=tenant_id,
                sender_phone=sender_phone,
                user_payload=user_payload,
                tenant_token=tenant_token,
                tenant_phone_id=tenant_phone_id,
                request_id=request_id,
                customer_name=customer_name,
            )

    elif msg_type == "interactive":
        # A button tap (Confirm / Cancel on an order summary).
        button = (msg.get("interactive") or {}).get("button_reply") or {}
        if button.get("id") and sender_phone:
            background_tasks.add_task(
                handle_button_reply,
                database=database,
                tenant=tenant,
                tenant_id=tenant_id,
                sender_phone=sender_phone,
                button_id=button["id"],
                button_title=button.get("title", ""),
                wamid=msg.get("id"),
                request_id=request_id,
            )

    elif msg_type == "audio":
        # Voice notes: transcribed in the background, then handled like a text message.
        media_id = (msg.get("audio") or {}).get("id")
        if media_id and sender_phone:
            background_tasks.add_task(
                handle_voice_turn,
                database=database,
                tenant=tenant,
                tenant_id=tenant_id,
                sender_phone=sender_phone,
                media_id=media_id,
                tenant_token=tenant_token,
                tenant_phone_id=tenant_phone_id,
                request_id=request_id,
                customer_name=customer_name,
            )

    # ---- 5. ACK in milliseconds ----
    return {"status": "success"}


# ---------------------------------------------------------------------------
# WhatsApp Status Webhook (delivered/read/failed)
# ---------------------------------------------------------------------------
@whatsapp_router.post("/status")
@alias_router.post("/status")
async def whatsapp_status_webhook(
    request: Request,
    database=Depends(get_database),
):
    """Handle WhatsApp message status callbacks (delivered/read/failed)."""
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        body = await request.json()
        logger.info(f"[{request_id}] Status webhook received: {body}")
        
        # Parse status update from Meta
        entry = body.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        statuses = value.get("statuses", [])
        
        for status_update in statuses:
            wamid = status_update.get("id")
            status = status_update.get("status")
            timestamp = status_update.get("timestamp")
            error = status_update.get("errors", [{}])[0] if status_update.get("errors") else None
            
            if wamid and status:
                await message_service.handle_status_webhook(
                    wamid=wamid,
                    status=status,
                    timestamp=int(timestamp) if timestamp else None,
                    error=error,
                )
        
        return {"status": "success"}
        
    except Exception as e:
        logger.exception(f"[{request_id}] Status webhook error: {e}")
        return {"status": "success"}  # Always ACK Meta