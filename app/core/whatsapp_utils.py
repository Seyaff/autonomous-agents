import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple

import httpx

from core.secrets import reveal
from core.settings import settings

logger = logging.getLogger(__name__)

GRAPH = "https://graph.facebook.com/v19.0"

# Meta error codes that mean the token or its permissions are the problem, not the message.
AUTH_ERROR_CODES = {190, 10, 200}


NOT_CONNECTED = "This restaurant hasn't connected its WhatsApp yet. Connect it in Settings."


def resolve_tenant_whatsapp_credentials(tenant: Optional[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (access_token, phone_number_id) for a tenant, or None for either one that
    the restaurant hasn't connected yet.

    Every restaurant uses its own Meta Embedded Signup credentials. Nothing falls back
    to a shared server-wide token, so one restaurant can never send as another.
    The stored token is decrypted here, and only here.
    """
    tenant = tenant or {}
    return reveal(tenant.get("whatsapp_access_token")), tenant.get("phone_number_id")


def _require_credentials(token: Optional[str], phone_number_id: Optional[str]) -> Optional[Tuple[str, str]]:
    if not token or not phone_number_id:
        return None
    return token, phone_number_id


@dataclass
class SendResult:
    ok: bool
    status: Optional[int] = None
    error_code: Optional[int] = None
    error_message: Optional[str] = None

    @property
    def auth_error(self) -> bool:
        return self.status in (401, 403) or self.error_code in AUTH_ERROR_CODES


def _meta_error(response: httpx.Response) -> Tuple[Optional[int], str]:
    try:
        err = response.json().get("error", {})
        return err.get("code"), err.get("message") or response.text
    except ValueError:
        return None, response.text


async def send_text(
    to_phone: str,
    text: str,
    token: Optional[str] = None,
    phone_number_id: Optional[str] = None,
) -> SendResult:
    """Sends a text message and says why it failed, so the caller can tell the owner."""
    creds = _require_credentials(token, phone_number_id)
    if creds is None:
        return SendResult(ok=False, error_message=NOT_CONNECTED)
    auth_token, phone_id = creds

    url = f"{GRAPH}/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {auth_token}",
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
        except httpx.RequestError as exc:
            logger.error(f"HTTP request error sending WhatsApp message: {exc}")
            return SendResult(ok=False, error_message=f"Could not reach WhatsApp: {exc}")

    if response.status_code in (200, 201):
        logger.info(f"Successfully sent WhatsApp message to {to_phone}")
        return SendResult(ok=True, status=response.status_code)

    code, message = _meta_error(response)
    logger.error(f"Meta WhatsApp API error ({response.status_code}): {response.text}")
    return SendResult(ok=False, status=response.status_code, error_code=code, error_message=message)


async def send_whatsapp_message(
    to_phone: str,
    text: str,
    token: Optional[str] = None,
    phone_number_id: Optional[str] = None,
) -> bool:
    """True/false wrapper around send_text, for callers that don't report failures."""
    result = await send_text(to_phone, text, token=token, phone_number_id=phone_number_id)
    return result.ok


async def verify_phone_number(token: str, phone_number_id: str) -> Dict[str, Any]:
    """Checks that the token can read this phone number and returns its public details.
    Raises ValueError with Meta's message if it can't."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{GRAPH}/{phone_number_id}",
            params={"fields": "display_phone_number,verified_name"},
            headers={"Authorization": f"Bearer {token}"},
        )
    if response.status_code != 200:
        _, message = _meta_error(response)
        raise ValueError(f"Meta could not confirm this phone number: {message}")
    return response.json()


async def subscribe_business_account(token: str, waba_id: str) -> None:
    """Asks Meta to send this business account's messages to our webhook.
    Without this, messages to the restaurant's number never reach the agent.
    Raises ValueError with Meta's message if it fails."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{GRAPH}/{waba_id}/subscribed_apps",
            headers={"Authorization": f"Bearer {token}"},
        )
    if response.status_code != 200 or response.json().get("success") is not True:
        _, message = _meta_error(response)
        raise ValueError(f"Meta would not connect the webhook to this account: {message}")


async def download_whatsapp_media(media_id: str, token: Optional[str] = None) -> bytes:
    """Fetches media URL using Meta's media_id and returns raw bytes from memory."""
    if not token:
        raise ValueError(NOT_CONNECTED)
    auth_token = token
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with httpx.AsyncClient(timeout=20.0) as client:
        # Step A: Resolve media ID to download URL
        media_info_url = f"{GRAPH}/{media_id}"
        resp = await client.get(media_info_url, headers=headers)
        if resp.status_code != 200:
            logger.error(f"Failed to fetch media metadata for ID {media_id}: {resp.text}")
            raise ValueError("Could not retrieve file metadata from WhatsApp API.")

        download_url = resp.json().get("url")
        if not download_url:
            raise ValueError("Media download URL missing from Meta response.")

        # Step B: Stream binary bytes directly into memory
        download_resp = await client.get(download_url, headers=headers)
        if download_resp.status_code != 200:
            logger.error(f"Failed to download media binary stream: {download_resp.text}")
            raise ValueError("Could not download file content from WhatsApp servers.")

        return download_resp.content


async def send_buttons(
    to_phone: str,
    body: str,
    buttons: list,
    token: Optional[str] = None,
    phone_number_id: Optional[str] = None,
) -> SendResult:
    """Sends a message with up to three tap-able buttons. Each button is {"id", "title"}.
    The customer's tap comes back to the webhook with the button's id."""
    creds = _require_credentials(token, phone_number_id)
    if creds is None:
        return SendResult(ok=False, error_message=NOT_CONNECTED)
    auth_token, phone_id = creds
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body[:1024]},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b["id"][:256], "title": b["title"][:20]}}
                    for b in buttons[:3]
                ]
            },
        },
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                f"{GRAPH}/{phone_id}/messages",
                json=payload,
                headers={"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"},
            )
        except httpx.RequestError as exc:
            return SendResult(ok=False, error_message=f"Could not reach WhatsApp: {exc}")
    if response.status_code in (200, 201):
        return SendResult(ok=True, status=response.status_code)
    code, message = _meta_error(response)
    logger.error(f"Meta WhatsApp buttons error ({response.status_code}): {response.text}")
    return SendResult(ok=False, status=response.status_code, error_code=code, error_message=message)
