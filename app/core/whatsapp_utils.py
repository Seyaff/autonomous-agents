import logging
from typing import Optional, Dict, Any, Tuple
import httpx
from core.settings import settings

logger = logging.getLogger(__name__)


def resolve_tenant_whatsapp_credentials(tenant: Optional[Dict[str, Any]]) -> Tuple[str, str]:
    """
    Returns (access_token, phone_number_id) for a tenant.

    Prefers the tenant's own connected WhatsApp (set via
    /tenant/meta-embedded-signup); falls back to the shared .env test
    credentials while Meta review/testing is pending — this is the one
    place that fallback lives, so flipping a tenant to real per-tenant
    credentials later needs no other code changes.
    """
    tenant = tenant or {}
    token = tenant.get("whatsapp_access_token") or settings.WHATSAPP_TOKEN
    phone_number_id = tenant.get("phone_number_id") or settings.WHATSAPP_PHONE_NUMBER_ID
    return token, phone_number_id


async def download_whatsapp_media(media_id: str, token: Optional[str] = None) -> bytes:
    """Fetches media URL using Meta's media_id and returns raw bytes from memory."""
    auth_token = token or settings.WHATSAPP_TOKEN
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with httpx.AsyncClient(timeout=20.0) as client:
        # Step A: Resolve media ID to download URL
        media_info_url = f"https://graph.facebook.com/v19.0/{media_id}"
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


async def send_whatsapp_message(
    to_phone: str,
    text: str,
    token: Optional[str] = None,
    phone_number_id: Optional[str] = None,
) -> bool:
    """Dispatches outbound text responses back to the user via Meta's WhatsApp Cloud API.
    Supports dynamic multi-tenant tokens and phone number IDs.
    """
    auth_token = token or settings.WHATSAPP_TOKEN
    phone_id = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID

    url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
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