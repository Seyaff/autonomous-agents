import logging
import httpx
from typing import Optional, List, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self):
        self.graph_url = settings.META_GRAPH_URL
        self.api_version = settings.META_API_VERSION
        self.default_token = settings.META_ACCESS_TOKEN

    async def send_text_message(
        self,
        to_phone: str,
        text: str,
        phone_number_id: Optional[str] = None,
        access_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a plain text message to a WhatsApp user."""
        token = access_token or self.default_token
        
        # If no credentials configured, log and return simulated response
        if not token or not phone_number_id:
            logger.info(f"[WHATSAPP SIMULATION] To: {to_phone} | Msg: {text}")
            return {"status": "simulated", "to": to_phone, "text": text}

        url = f"{self.graph_url}/{self.api_version}/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "text",
            "text": {"preview_url": False, "body": text}
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=headers, json=payload, timeout=10.0)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Failed to send WhatsApp message to {to_phone}: {e}")
                return {"error": str(e), "status": "failed"}

    async def send_interactive_buttons(
        self,
        to_phone: str,
        body_text: str,
        buttons: List[Dict[str, str]], # [{"id": "btn_1", "title": "Confirm Order"}]
        phone_number_id: Optional[str] = None,
        access_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send quick reply interactive buttons."""
        token = access_token or self.default_token
        if not token or not phone_number_id:
            logger.info(f"[WHATSAPP SIMULATION BUTTONS] To: {to_phone} | Body: {body_text} | Buttons: {buttons}")
            return {"status": "simulated", "buttons": buttons}

        url = f"{self.graph_url}/{self.api_version}/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        formatted_buttons = [
            {
                "type": "reply",
                "reply": {"id": b["id"], "title": b["title"][:20]} # Meta max 20 chars
            }
            for b in buttons[:3] # Meta max 3 quick buttons
        ]

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body_text},
                "action": {"buttons": formatted_buttons}
            }
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=headers, json=payload, timeout=10.0)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Failed to send WhatsApp buttons to {to_phone}: {e}")
                return {"error": str(e), "status": "failed"}

    async def download_media_bytes(
        self,
        media_id: str,
        access_token: Optional[str] = None
    ) -> Optional[bytes]:
        """Download raw file bytes (PDF, Image) from Meta WhatsApp Cloud API."""
        token = access_token or self.default_token
        if not token:
            logger.warning("Cannot download media: No Meta access token configured.")
            return None

        # Step 1: Retrieve media metadata and direct download URL
        meta_url = f"{self.graph_url}/{self.api_version}/{media_id}"
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient() as client:
            try:
                meta_resp = await client.get(meta_url, headers=headers, timeout=15.0)
                meta_resp.raise_for_status()
                file_url = meta_resp.json().get("url")
                if not file_url:
                    logger.error(f"No download URL returned for media_id {media_id}")
                    return None

                # Step 2: Download raw binary bytes with Authorization header
                file_resp = await client.get(file_url, headers=headers, timeout=30.0)
                file_resp.raise_for_status()
                return file_resp.content
            except httpx.HTTPError as e:
                logger.error(f"Failed to download Meta WhatsApp media {media_id}: {e}")
                return None

whatsapp_service = WhatsAppService()
