import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from pymongo.errors import DuplicateKeyError

from api.v1.endpoints.whatsapp import handle_button_reply, handle_text_turn
from core.database import get_database
from core.instagram_utils import authorize_url, configured, customer_profile, download, igsid_of, signature_ok
from core.settings import settings
from middlewares.auth_middleware import require_owner
from services.channels import instagram_credentials, send_text_to
from services.instagram import InstagramEvent, connect_account, disconnect_account, make_state, parse_events, read_state

logger = logging.getLogger(__name__)

instagram_router = APIRouter(prefix="/instagram", tags=["Instagram"])

UNREADABLE = "[the customer sent a photo, video or file the agent can't open]"
VOICE_FALLBACK = "Voice note samajh nahi aayi. Please text mein likh dein."


# ---------------------------------------------------------------------------
# Connecting the account
# ---------------------------------------------------------------------------
@instagram_router.get("/connect-url")
async def connect_url(current_user: dict = Depends(require_owner)):
    """Where to send the owner to sign in with Instagram."""
    if not configured():
        raise HTTPException(status_code=503, detail="Instagram isn't set up on the server yet. Ask the team to add the Instagram app.")
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Create your business first.")
    return {"url": authorize_url(make_state(tenant_id, str(current_user.get("user_id"))))}


def _back_to_settings(**params: str) -> RedirectResponse:
    return RedirectResponse(f"{settings.frontend_origin}/dashboard/settings?{urlencode(params)}", status_code=302)


@instagram_router.get("/callback")
async def connect_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    db=Depends(get_database),
):
    """Instagram sends the owner back here after they sign in. The signed state says which business."""
    if not state:
        return _back_to_settings(instagram_error="Instagram didn't finish the sign-in. Try again.")
    try:
        who = read_state(state)
    except ValueError as e:
        return _back_to_settings(instagram_error=str(e))
    if not code:
        return _back_to_settings(instagram_error=error_description or "You cancelled the Instagram sign-in.")
    try:
        fields = await connect_account(db, who["tenant_id"], code)
    except ValueError as e:
        logger.warning(f"[instagram-connect] failed tenant={who['tenant_id']}: {e}")
        await db["tenants"].update_one(
            {"tenant_id": who["tenant_id"]},
            {"$set": {"instagram_status": "error", "instagram_last_error": str(e), "updated_at": datetime.now(timezone.utc)}},
        )
        return _back_to_settings(instagram_error=str(e))
    logger.info(f"[instagram-connect] tenant={who['tenant_id']} connected @{fields.get('instagram_username')}")
    return _back_to_settings(instagram="connected")


@instagram_router.post("/disconnect")
async def disconnect(db=Depends(get_database), current_user: dict = Depends(require_owner)):
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active business found.")
    await disconnect_account(db, tenant_id)
    return {"status": "disconnected"}


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------
@instagram_router.get("/webhook")
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
):
    expected = settings.INSTAGRAM_VERIFY_TOKEN or settings.WHATSAPP_VERIFY_TOKEN
    if hub_mode == "subscribe" and hub_verify_token == expected:
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Verification token mismatch", status_code=status.HTTP_403_FORBIDDEN)


@instagram_router.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks, db=Depends(get_database)):
    """Instagram DMs. Each one is checked, deduplicated, and handled in the background like a WhatsApp message."""
    request_id = getattr(request.state, "request_id", "unknown")
    raw = await request.body()
    if not signature_ok(raw, request.headers.get("x-hub-signature-256")):
        logger.warning(f"[{request_id}] Instagram webhook with a bad signature was refused")
        return Response(content="Bad signature", status_code=status.HTTP_403_FORBIDDEN)
    try:
        body = await request.json()
    except Exception:
        return Response(content="Invalid JSON", status_code=status.HTTP_400_BAD_REQUEST)

    tenants: Dict[str, Optional[Dict[str, Any]]] = {}
    for event in parse_events(body):
        if event.account_id not in tenants:
            tenants[event.account_id] = await db["tenants"].find_one({"instagram_account_id": event.account_id})
        tenant = tenants[event.account_id]
        if not tenant:
            logger.warning(f"[{request_id}] No business is connected to Instagram account {event.account_id}")
            continue
        if event.mid:
            try:
                await db["processed_messages"].insert_one({
                    "message_id": event.mid,
                    "tenant_id": tenant["tenant_id"],
                    "sender_phone": event.contact,
                    "msg_type": f"instagram_{event.kind}",
                    "received_at": datetime.utcnow(),
                })
            except DuplicateKeyError:
                continue
        background_tasks.add_task(handle_instagram_event, db, tenant, event, request_id)
    return {"status": "success"}


async def handle_instagram_event(db, tenant: Dict[str, Any], event: InstagramEvent, request_id: str = "bg") -> None:
    tenant_id = tenant["tenant_id"]
    if event.kind == "tap":
        await handle_button_reply(
            database=db, tenant=tenant, tenant_id=tenant_id, sender_phone=event.contact,
            button_id=event.payload, button_title=event.text or event.payload, wamid=event.mid, request_id=request_id,
        )
        return

    name, username = await _customer_names(db, tenant, event.contact)
    text = event.text
    if event.kind == "audio":
        text = await _transcribe(event.url, request_id, event.contact)
        if not text:
            await send_text_to(tenant, event.contact, VOICE_FALLBACK, db)
            return
    elif event.kind == "unsupported":
        text = UNREADABLE

    await handle_text_turn(
        database=db, tenant=tenant, tenant_id=tenant_id, sender_phone=event.contact, user_payload=text,
        tenant_token=None, tenant_phone_id=None, request_id=request_id,
        customer_name=name, wamid=event.mid, customer_username=username,
    )


async def _customer_names(db, tenant: Dict[str, Any], contact: str):
    """The customer's name and @username, asked of Instagram the first time they write."""
    existing = await db["conversations"].find_one(
        {"tenant_id": tenant["tenant_id"], "customer_phone": contact}, {"customer_name": 1, "customer_username": 1}
    )
    if existing and existing.get("customer_name"):
        return existing["customer_name"], existing.get("customer_username")
    token, _ = await instagram_credentials(tenant, db)
    if not token:
        return "", None
    profile = await customer_profile(token, igsid_of(contact))
    username = profile.get("username")
    return profile.get("name") or (f"@{username}" if username else ""), username


async def _transcribe(url: str, request_id: str, contact: str) -> str:
    from services.voice_transcription import TranscriptionError, transcribe_urdu_audio

    try:
        transcript = await transcribe_urdu_audio(await download(url))
    except (ValueError, TranscriptionError) as e:
        logger.warning(f"[{request_id}] Instagram voice note from {contact} not transcribed: {e}")
        return ""
    except Exception as e:
        logger.exception(f"[{request_id}] Instagram voice note from {contact} failed: {e}")
        return ""
    return f"[voice note] {transcript}" if transcript else ""
