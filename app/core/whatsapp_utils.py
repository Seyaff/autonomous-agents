import logging
import httpx
from core.settings import settings

logger = logging.getLogger(__name__)


async def download_whatsapp_media(media_id: str) -> bytes:
    """Fetches media URL using Meta's media_id and returns raw bytes from memory."""
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"}

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