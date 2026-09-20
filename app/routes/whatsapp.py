import logging
from typing import Optional
import httpx
from fastapi import APIRouter, Request, Query, Response, status, BackgroundTasks
from langchain_core.messages import HumanMessage
from core.whatsapp_utils import download_whatsapp_media, send_whatsapp_message
from services.pdf_ingestion import process_and_store_pdf_bytes

from core.settings import settings
from agents.customer_support.agent import master_agent

logger = logging.getLogger(__name__)

whatsapp_router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Webhook"])
alias_router = APIRouter(prefix="/whatsapp/webhook", tags=["WhatsApp Webhook"])


async def send_whatsapp_message(to_phone: str, text: str) -> bool:
    """Dispatches outbound text responses back to the user via Meta's WhatsApp Cloud API."""
    url = f"https://graph.facebook.com/v19.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code in [200, 201]:
                logger.info(f"Successfully sent WhatsApp message to {to_phone}")
                return True
            else:
                logger.error(
                    f"Meta WhatsApp API error ({response.status_code}): {response.text}"
                )
                return False
        except httpx.RequestError as exc:
            logger.error(f"HTTP request error sending WhatsApp message: {exc}")
            return False


@whatsapp_router.get("")
@alias_router.get("")
async def verify_meta_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token")
):
    """Meta Webhook handshake verification endpoint."""
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("Meta webhook verification successful.")
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Verification token mismatch", status_code=status.HTTP_403_FORBIDDEN)


async def handle_inbound_pdf(media_id: str, filename: str, sender_phone: str):
    """Background task to download PDF, split chunks, upsert vectors, and notify user."""
    try:
        await send_whatsapp_message(
            to_phone=sender_phone,
            text=f"📄 Processing '{filename}'... I am reading and indexing your document.",
        )

        file_bytes = await download_whatsapp_media(media_id)

        # Uses sender phone number as the isolated Pinecone namespace/tenant_id
        num_chunks = await process_and_store_pdf_bytes(
            file_bytes=file_bytes,
            filename=filename,
            tenant_id=sender_phone,
        )

        if num_chunks > 0:
            reply = f"✅ Finished indexing '{filename}' ({num_chunks} chunks). You can now ask me questions about it!"
        else:
            reply = f"⚠️ Could not extract readable text from '{filename}'. Please ensure it is not a scanned image PDF."

    except Exception as e:
        logger.error(f"Error executing PDF ingestion background task for {sender_phone}: {e}")
        reply = "❌ An error occurred while processing your PDF document."

    await send_whatsapp_message(to_phone=sender_phone, text=reply)


@whatsapp_router.get("")
@alias_router.get("")
async def verify_meta_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
):
    """Meta Webhook handshake verification endpoint."""
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("Meta webhook verification successful.")
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Verification token mismatch", status_code=status.HTTP_403_FORBIDDEN)


@whatsapp_router.post("")
@alias_router.post("")
async def receive_meta_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receive inbound WhatsApp webhooks and route between document parsing and Agent invocation."""
    try:
        body = await request.json()
    except Exception:
        return Response(content="Invalid JSON", status_code=status.HTTP_400_BAD_REQUEST)

    try:
        entry = body.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if messages:
            msg = messages[0]
            sender_phone = msg.get("from")
            msg_type = msg.get("type")

            # --- ROUTE 1: INBOUND DOCUMENT (PDF / MENU) ---
            if msg_type == "document":
                doc_meta = msg.get("document", {})
                mime_type = doc_meta.get("mime_type", "")
                media_id = doc_meta.get("id")
                filename = doc_meta.get("filename", "document.pdf")

                if "pdf" in mime_type and media_id and sender_phone:
                    # Offload work to background task to acknowledge Meta within 3 seconds
                    background_tasks.add_task(
                        handle_inbound_pdf,
                        media_id=media_id,
                        filename=filename,
                        sender_phone=sender_phone,
                    )
                    return {"status": "success"}

            # --- ROUTE 2: INBOUND TEXT QUERY ---
            user_payload = None
            if msg_type == "text":
                user_payload = msg.get("text", {}).get("body", "")

            if user_payload and sender_phone:
                # Binds session memory to caller's phone number
                config = {"configurable": {"thread_id": sender_phone}}

                # Asynchronously invoke master_agent workflow
                agent_result = await master_agent.ainvoke(
                    {"messages": [HumanMessage(content=user_payload)]},
                    config=config,
                )

                # Extract last message from agent response
                last_message = agent_result["messages"][-1]
                if isinstance(last_message.content, list):
                    reply_text = "".join(
                        block.get("text", "")
                        for block in last_message.content
                        if isinstance(block, dict)
                    )
                else:
                    reply_text = last_message.content or ""

                if reply_text:
                    logger.info(f"Agent reply to [{sender_phone}]: {reply_text}")
                    await send_whatsapp_message(to_phone=sender_phone, text=reply_text)

    except (IndexError, AttributeError, KeyError) as e:
        logger.error(f"Error parsing webhook payload: {e}")

    # Always respond with 200 OK to prevent Meta from retrying webhooks
    return {"status": "success"}