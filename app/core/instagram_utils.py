"""
Instagram API with Instagram Login: connecting a professional account, and sending DMs.

Customers are identified by their Instagram-scoped id (IGSID). Inside this app a customer's
contact key is "ig:<IGSID>", stored where WhatsApp customers keep their phone number, so the
inbox, orders and memory work the same for both channels.
"""

import hashlib
import hmac
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from core.settings import settings
from core.whatsapp_utils import SendResult

logger = logging.getLogger(__name__)

IG_GRAPH = "https://graph.instagram.com/v23.0"
IG_GRAPH_UNVERSIONED = "https://graph.instagram.com"
AUTHORIZE_URL = "https://www.instagram.com/oauth/authorize"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"
SCOPES = "instagram_business_basic,instagram_business_manage_messages"

CONTACT_PREFIX = "ig:"
AUTH_ERROR_CODES = {190, 10, 200}


def contact_key(igsid: str) -> str:
    return f"{CONTACT_PREFIX}{igsid}"


def is_instagram(contact: Optional[str]) -> bool:
    return bool(contact) and contact.startswith(CONTACT_PREFIX)


def igsid_of(contact: str) -> str:
    return contact[len(CONTACT_PREFIX):] if is_instagram(contact) else contact


def configured() -> bool:
    return bool(settings.INSTAGRAM_APP_ID and settings.INSTAGRAM_APP_SECRET)


def redirect_uri() -> str:
    return f"{settings.PUBLIC_API_BASE.rstrip('/')}/instagram/callback"


def authorize_url(state: str) -> str:
    return AUTHORIZE_URL + "?" + urlencode({
        "client_id": settings.INSTAGRAM_APP_ID,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
    })


def signature_ok(body: bytes, header: Optional[str]) -> bool:
    """Meta signs each webhook with the app secret. Without a secret configured nothing can be checked."""
    if not settings.INSTAGRAM_APP_SECRET:
        return True
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(settings.INSTAGRAM_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[len("sha256="):])


def _error(response: httpx.Response) -> tuple:
    try:
        err = response.json().get("error") or {}
        if isinstance(err, dict):
            return err.get("code"), err.get("error_user_msg") or err.get("message") or response.text
        return None, response.json().get("error_message") or str(err)
    except ValueError:
        return None, response.text


async def exchange_code(code: str) -> Dict[str, Any]:
    """Code from the login redirect -> short-lived token. Raises ValueError with Meta's message."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(TOKEN_URL, data={
            "client_id": settings.INSTAGRAM_APP_ID,
            "client_secret": settings.INSTAGRAM_APP_SECRET,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri(),
            "code": code,
        })
    if response.status_code != 200:
        _, message = _error(response)
        raise ValueError(f"Instagram didn't accept the sign-in: {message}")
    data = response.json()
    # Some responses wrap it in a "data" list.
    if isinstance(data.get("data"), list) and data["data"]:
        return data["data"][0]
    return data


async def long_lived_token(short_token: str) -> Dict[str, Any]:
    """Short-lived token -> 60-day token. Returns {"access_token", "expires_in"}."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(f"{IG_GRAPH_UNVERSIONED}/access_token", params={
            "grant_type": "ig_exchange_token",
            "client_secret": settings.INSTAGRAM_APP_SECRET,
            "access_token": short_token,
        })
    if response.status_code != 200:
        _, message = _error(response)
        raise ValueError(f"Instagram didn't give a lasting token: {message}")
    return response.json()


async def refresh_token(token: str) -> Dict[str, Any]:
    """Renews a 60-day token (it must be at least a day old). Returns {"access_token", "expires_in"}."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(f"{IG_GRAPH_UNVERSIONED}/refresh_access_token", params={
            "grant_type": "ig_refresh_token",
            "access_token": token,
        })
    if response.status_code != 200:
        _, message = _error(response)
        raise ValueError(f"Instagram didn't renew the token: {message}")
    return response.json()


async def account_profile(token: str) -> Dict[str, Any]:
    """The connected account: user_id (the id webhooks use), username, name."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(f"{IG_GRAPH}/me", params={
            "fields": "user_id,username,name,profile_picture_url",
            "access_token": token,
        })
    if response.status_code != 200:
        _, message = _error(response)
        raise ValueError(f"Instagram didn't share the account details: {message}")
    return response.json()


async def subscribe_account(token: str) -> None:
    """Asks Instagram to send this account's DMs to our webhook."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(f"{IG_GRAPH}/me/subscribed_apps", params={
            "subscribed_fields": "messages,messaging_postbacks",
            "access_token": token,
        })
    if response.status_code != 200 or response.json().get("success") is not True:
        _, message = _error(response)
        raise ValueError(f"Instagram would not send this account's messages to us: {message}")


async def customer_profile(token: str, igsid: str) -> Dict[str, Any]:
    """A customer's name and username, when Instagram shares them. Empty if it doesn't."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{IG_GRAPH}/{igsid}", params={"fields": "name,username", "access_token": token})
        return response.json() if response.status_code == 200 else {}
    except httpx.RequestError:
        return {}


async def _send(token: Optional[str], account_id: Optional[str], payload: Dict[str, Any]) -> SendResult:
    if not token or not account_id:
        return SendResult(ok=False, error_message="This business hasn't connected Instagram. Connect it in Settings.")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                f"{IG_GRAPH}/{account_id}/messages",
                json=payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
        except httpx.RequestError as exc:
            return SendResult(ok=False, error_message=f"Could not reach Instagram: {exc}")
    if response.status_code == 200:
        return SendResult(ok=True, status=200, message_id=response.json().get("message_id"))
    code, message = _error(response)
    logger.error(f"Instagram send error ({response.status_code}): {response.text}")
    return SendResult(ok=False, status=response.status_code, error_code=code, error_message=message)


async def send_dm(token: Optional[str], account_id: Optional[str], igsid: str, text: str) -> SendResult:
    """A text DM. Instagram allows 1,000 characters per message, so longer text is split."""
    parts = [text[i:i + 1000] for i in range(0, len(text), 1000)] or [""]
    result = SendResult(ok=False)
    for part in parts:
        result = await _send(token, account_id, {"recipient": {"id": igsid}, "message": {"text": part}})
        if not result.ok:
            break
    return result


async def send_quick_replies(
    token: Optional[str], account_id: Optional[str], igsid: str, text: str, buttons: List[Dict[str, str]]
) -> SendResult:
    """Text with tap-able replies. A tap comes back as a message with quick_reply.payload set to the button id."""
    return await _send(token, account_id, {
        "recipient": {"id": igsid},
        "message": {
            "text": text[:1000],
            "quick_replies": [
                {"content_type": "text", "title": b["title"][:20], "payload": b["id"][:1000]} for b in buttons[:13]
            ],
        },
    })


async def download(url: str) -> bytes:
    """Instagram attachment URLs (voice notes) are signed links that need no token."""
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(url)
    if response.status_code != 200:
        raise ValueError("Could not download the attachment from Instagram.")
    return response.content
