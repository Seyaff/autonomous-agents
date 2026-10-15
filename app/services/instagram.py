"""
Connecting a business's Instagram account, and reading what its webhook sends.

The owner signs in with Instagram from Settings. The callback exchanges the code for a
60-day token, checks the account isn't already connected to another business, and
subscribes it to our webhook. DMs then reach the same agent and inbox as WhatsApp.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import jwt

from core.instagram_utils import (
    account_profile,
    contact_key,
    exchange_code,
    long_lived_token,
    subscribe_account,
)
from core.secrets import protect
from core.settings import settings

logger = logging.getLogger(__name__)

STATE_MINUTES = 15
STATE_AUDIENCE = "instagram-connect"


def make_state(tenant_id: str, user_id: str) -> str:
    """Signed, short-lived proof that this sign-in was started by this owner for this business."""
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"tid": tenant_id, "uid": user_id, "aud": STATE_AUDIENCE, "iat": now, "exp": now + timedelta(minutes=STATE_MINUTES)},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def read_state(state: str) -> Dict[str, str]:
    """Raises ValueError if the state is forged, for another purpose, or expired."""
    try:
        claims = jwt.decode(state, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM], audience=STATE_AUDIENCE)
    except jwt.PyJWTError:
        raise ValueError("That Instagram sign-in link has expired. Start again from Settings.")
    return {"tenant_id": claims["tid"], "user_id": claims["uid"]}


async def connect_account(db, tenant_id: str, code: str) -> Dict[str, Any]:
    """Everything that must pass before the account counts as connected. Raises ValueError with a reason."""
    short = await exchange_code(code)
    token_info = await long_lived_token(short["access_token"])
    token = token_info["access_token"]
    profile = await account_profile(token)
    account_id = str(profile.get("user_id") or profile.get("id") or "")
    if not account_id:
        raise ValueError("Instagram didn't say which account this is. Try again.")

    other = await db["tenants"].find_one(
        {"instagram_account_id": account_id, "tenant_id": {"$ne": tenant_id}}, {"tenant_id": 1}
    )
    if other:
        raise ValueError("This Instagram account is already connected to another business.")

    await subscribe_account(token)
    now = datetime.now(timezone.utc)
    fields = {
        "instagram_account_id": account_id,
        "instagram_username": profile.get("username"),
        "instagram_access_token": protect(token),
        "instagram_token_issued_at": now,
        "instagram_token_expires_at": now + timedelta(seconds=int(token_info.get("expires_in") or 5184000)),
        "instagram_connected": True,
        "instagram_status": "connected",
        "instagram_last_error": None,
        "updated_at": now,
    }
    await db["tenants"].update_one({"tenant_id": tenant_id}, {"$set": fields})
    return fields


async def disconnect_account(db, tenant_id: str) -> None:
    await db["tenants"].update_one({"tenant_id": tenant_id}, {
        "$set": {"instagram_connected": False, "instagram_status": "disconnected", "updated_at": datetime.now(timezone.utc)},
        "$unset": {"instagram_access_token": "", "instagram_account_id": "", "instagram_token_expires_at": ""},
    })


@dataclass
class InstagramEvent:
    """One thing a customer did in DMs, in the shape the shared handlers take."""
    account_id: str
    contact: str          # "ig:<IGSID>"
    mid: Optional[str]
    kind: str             # "text", "tap", "audio", "unsupported"
    text: str = ""
    payload: str = ""     # a quick-reply or postback id
    url: str = ""         # an audio attachment


def parse_events(body: Dict[str, Any]) -> List[InstagramEvent]:
    """Reads Instagram's webhook body. Our own sends (echoes), read receipts and reactions are skipped."""
    events: List[InstagramEvent] = []
    for entry in body.get("entry") or []:
        account_id = str(entry.get("id") or "")
        for item in entry.get("messaging") or []:
            sender = str((item.get("sender") or {}).get("id") or "")
            if not sender or sender == account_id:
                continue
            message = item.get("message")
            postback = item.get("postback")
            if message:
                if message.get("is_echo") or message.get("is_deleted"):
                    continue
                mid = message.get("mid")
                quick = (message.get("quick_reply") or {}).get("payload")
                if quick:
                    events.append(InstagramEvent(account_id, contact_key(sender), mid, "tap", text=message.get("text") or "", payload=quick))
                    continue
                if message.get("text"):
                    events.append(InstagramEvent(account_id, contact_key(sender), mid, "text", text=message["text"]))
                    continue
                audio = next((a for a in message.get("attachments") or [] if a.get("type") == "audio"), None)
                if audio and (audio.get("payload") or {}).get("url"):
                    events.append(InstagramEvent(account_id, contact_key(sender), mid, "audio", url=audio["payload"]["url"]))
                    continue
                events.append(InstagramEvent(account_id, contact_key(sender), mid, "unsupported"))
            elif postback and postback.get("payload"):
                events.append(InstagramEvent(account_id, contact_key(sender), postback.get("mid"), "tap",
                                             text=postback.get("title") or "", payload=postback["payload"]))
    return events
