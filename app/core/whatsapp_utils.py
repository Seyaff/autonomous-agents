import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx

from core.secrets import reveal
from core.settings import settings

logger = logging.getLogger(__name__)

GRAPH = "https://graph.facebook.com/v19.0"

# Meta error codes that mean the token or its permissions are the problem, not the message.
AUTH_ERROR_CODES = {190, 10, 200}


NOT_CONNECTED = "This business hasn't connected its WhatsApp yet. Connect it in Settings."


def resolve_tenant_whatsapp_credentials(tenant: Optional[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (access_token, phone_number_id) for a tenant, or None for either one that
    the business hasn't connected yet.

    Every business uses its own Meta Embedded Signup credentials. Nothing falls back
    to a shared server-wide token, so one business can never send as another.
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
    # Meta's id for the sent message (the wamid). Delivery and read receipts refer to it.
    message_id: Optional[str] = None

    @property
    def auth_error(self) -> bool:
        return self.status in (401, 403) or self.error_code in AUTH_ERROR_CODES


def _meta_error(response: httpx.Response) -> Tuple[Optional[int], str]:
    try:
        err = response.json().get("error", {})
        return err.get("code"), err.get("error_user_msg") or err.get("message") or response.text
    except ValueError:
        return None, response.text


def _sent_id(response: httpx.Response) -> Optional[str]:
    try:
        return (response.json().get("messages") or [{}])[0].get("id")
    except (ValueError, AttributeError, IndexError):
        return None


async def _post_message(phone_id: str, auth_token: str, payload: Dict[str, Any], what: str) -> SendResult:
    """Posts one message to the Cloud API and reports what happened."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                f"{GRAPH}/{phone_id}/messages",
                json={"messaging_product": "whatsapp", "recipient_type": "individual", **payload},
                headers={"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"},
            )
        except httpx.RequestError as exc:
            logger.error(f"HTTP request error sending WhatsApp {what}: {exc}")
            return SendResult(ok=False, error_message=f"Could not reach WhatsApp: {exc}")

    if response.status_code in (200, 201):
        return SendResult(ok=True, status=response.status_code, message_id=_sent_id(response))

    code, message = _meta_error(response)
    logger.error(f"Meta WhatsApp {what} error ({response.status_code}): {response.text}")
    return SendResult(ok=False, status=response.status_code, error_code=code, error_message=message)


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
    result = await _post_message(
        phone_id,
        auth_token,
        {"to": to_phone, "type": "text", "text": {"preview_url": False, "body": text}},
        "message",
    )
    if result.ok:
        logger.info(f"Successfully sent WhatsApp message to {to_phone}")
    return result


async def send_template(
    to_phone: str,
    name: str,
    language: str,
    components: Optional[List[Dict[str, Any]]] = None,
    token: Optional[str] = None,
    phone_number_id: Optional[str] = None,
) -> SendResult:
    """Sends an approved message template. Templates are the only messages Meta lets a business
    send more than 24 hours after the customer last wrote."""
    creds = _require_credentials(token, phone_number_id)
    if creds is None:
        return SendResult(ok=False, error_message=NOT_CONNECTED)
    auth_token, phone_id = creds
    template: Dict[str, Any] = {"name": name, "language": {"code": language}}
    if components:
        template["components"] = components
    return await _post_message(phone_id, auth_token, {"to": to_phone, "type": "template", "template": template}, "template")


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
    Without this, messages to the business's number never reach the agent.
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
    return await _post_message(phone_id, auth_token, payload, "buttons")


# ---------------------------------------------------------------------------
# Message templates on the business account (WABA)
# ---------------------------------------------------------------------------
TEMPLATE_FIELDS = "id,name,language,status,category,components,rejected_reason"


async def list_templates(token: str, waba_id: str) -> List[Dict[str, Any]]:
    """Every template on the business account, following Meta's paging. Raises ValueError with Meta's message."""
    templates: List[Dict[str, Any]] = []
    url: Optional[str] = f"{GRAPH}/{waba_id}/message_templates"
    params: Optional[Dict[str, Any]] = {"fields": TEMPLATE_FIELDS, "limit": 100}
    async with httpx.AsyncClient(timeout=20.0) as client:
        for _ in range(20):  # 2,000 templates, more than Meta allows on one account
            if not url:
                break
            response = await client.get(url, params=params, headers={"Authorization": f"Bearer {token}"})
            if response.status_code != 200:
                _, message = _meta_error(response)
                raise ValueError(f"Meta would not list the templates: {message}")
            data = response.json()
            templates.extend(data.get("data") or [])
            url = (data.get("paging") or {}).get("next")
            params = None  # the next link already carries them
    return templates


async def create_template(token: str, waba_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Submits a template for Meta's review. Returns {"id", "status", "category"}.
    Raises ValueError with Meta's message."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{GRAPH}/{waba_id}/message_templates",
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
    if response.status_code not in (200, 201):
        _, message = _meta_error(response)
        raise ValueError(f"Meta didn't accept the template: {message}")
    return response.json()


async def delete_template(token: str, waba_id: str, name: str, template_id: Optional[str] = None) -> None:
    """Deletes a template. With an id only that language version goes; without, every language of the name.
    Raises ValueError with Meta's message."""
    params: Dict[str, Any] = {"name": name}
    if template_id:
        params["hsm_id"] = template_id
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.delete(
            f"{GRAPH}/{waba_id}/message_templates", params=params, headers={"Authorization": f"Bearer {token}"}
        )
    if response.status_code != 200:
        _, message = _meta_error(response)
        raise ValueError(f"Meta would not delete the template: {message}")


# ---------------------------------------------------------------------------
# WhatsApp Flows (in-chat forms)
# ---------------------------------------------------------------------------
def _flow_errors(data: Dict[str, Any]) -> List[str]:
    """Meta's validation errors for a Flow JSON, as short lines the owner can read."""
    lines = []
    for err in data.get("validation_errors") or []:
        where = err.get("pointers") or []
        place = f" ({where[0].get('path')})" if where and where[0].get("path") else ""
        lines.append(f"{err.get('error_type') or 'Error'}: {err.get('message') or ''}{place}".strip())
    return lines


async def create_flow(token: str, waba_id: str, name: str, categories: List[str]) -> str:
    """Creates an empty draft Flow and returns its id. Raises ValueError with Meta's message."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{GRAPH}/{waba_id}/flows",
            json={"name": name, "categories": categories},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
    if response.status_code not in (200, 201) or not response.json().get("id"):
        _, message = _meta_error(response)
        raise ValueError(f"Meta didn't create the form: {message}")
    return response.json()["id"]


async def upload_flow_json(token: str, flow_id: str, flow_json: str) -> List[str]:
    """Uploads the form's Flow JSON. Returns Meta's validation errors; an empty list means it's valid.
    Raises ValueError if Meta refuses the upload itself."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{GRAPH}/{flow_id}/assets",
            data={"name": "flow.json", "asset_type": "FLOW_JSON"},
            files={"file": ("flow.json", flow_json.encode("utf-8"), "application/json")},
            headers={"Authorization": f"Bearer {token}"},
        )
    if response.status_code not in (200, 201):
        _, message = _meta_error(response)
        raise ValueError(f"Meta didn't accept the form: {message}")
    return _flow_errors(response.json())


async def publish_flow(token: str, flow_id: str) -> None:
    """Publishes a draft Flow so it can be sent to anyone. A published Flow can't be changed.
    Raises ValueError with Meta's message."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(f"{GRAPH}/{flow_id}/publish", headers={"Authorization": f"Bearer {token}"})
    if response.status_code != 200 or response.json().get("success") is not True:
        _, message = _meta_error(response)
        raise ValueError(f"Meta didn't publish the form: {message}")


async def retire_flow(token: str, flow_id: str, published: bool) -> None:
    """Removes a Flow from use: a draft is deleted, a published one is deprecated.
    Never raises: a Flow Meta can't find or retire doesn't stop the owner."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            if published:
                response = await client.post(f"{GRAPH}/{flow_id}/deprecate", headers={"Authorization": f"Bearer {token}"})
            else:
                response = await client.delete(f"{GRAPH}/{flow_id}", headers={"Authorization": f"Bearer {token}"})
        except httpx.RequestError as exc:
            logger.warning(f"Could not retire flow {flow_id}: {exc}")
            return
    if response.status_code != 200:
        logger.warning(f"Meta did not retire flow {flow_id}: {response.text}")


async def flow_preview_url(token: str, flow_id: str) -> Optional[str]:
    """A web link that shows the form the way customers will see it. None if Meta doesn't give one."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{GRAPH}/{flow_id}",
            params={"fields": "preview.invalidate(false)"},
            headers={"Authorization": f"Bearer {token}"},
        )
    if response.status_code != 200:
        return None
    return (response.json().get("preview") or {}).get("preview_url")


async def send_flow(
    to_phone: str,
    flow_id: str,
    flow_token: str,
    first_screen: str,
    body: str,
    cta: str,
    token: Optional[str] = None,
    phone_number_id: Optional[str] = None,
    draft: bool = False,
) -> SendResult:
    """Sends a message with a button that opens the form. The customer's answers come back
    to the webhook as an nfm_reply carrying flow_token."""
    creds = _require_credentials(token, phone_number_id)
    if creds is None:
        return SendResult(ok=False, error_message=NOT_CONNECTED)
    auth_token, phone_id = creds
    parameters: Dict[str, Any] = {
        "flow_message_version": "3",
        "flow_token": flow_token,
        "flow_id": flow_id,
        "flow_cta": cta[:30],
        "flow_action": "navigate",
        "flow_action_payload": {"screen": first_screen},
    }
    if draft:
        parameters["mode"] = "draft"
    payload = {
        "to": to_phone,
        "type": "interactive",
        "interactive": {
            "type": "flow",
            "body": {"text": body[:1024]},
            "action": {"name": "flow", "parameters": parameters},
        },
    }
    return await _post_message(phone_id, auth_token, payload, "form")
