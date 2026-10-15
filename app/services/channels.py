"""
One way to message a customer, whichever app they wrote from.

A contact key is a WhatsApp number ("923001234567") or an Instagram customer ("ig:<IGSID>").
Everything that replies to a customer (the agent, the owner, order updates, confirmations)
sends through here, so it reaches the customer in the app they used.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.instagram_utils import igsid_of, is_instagram, refresh_token, send_dm, send_quick_replies
from core.secrets import protect, reveal
from core.whatsapp_utils import SendResult, resolve_tenant_whatsapp_credentials, send_buttons, send_text

logger = logging.getLogger(__name__)

# A 60-day Instagram token is renewed once it has less than this left.
RENEW_WITHIN = timedelta(days=10)
# Instagram refuses to renew a token less than a day old.
RENEW_MIN_AGE = timedelta(days=1)


def channel_of(contact: Optional[str]) -> str:
    return "instagram" if is_instagram(contact) else "whatsapp"


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def instagram_credentials(tenant: Dict[str, Any], db=None) -> Tuple[Optional[str], Optional[str]]:
    """(token, account id) for the business's Instagram. Renews the token when it's close to expiring.
    Renewal failures are logged, never raised: the old token works until it expires."""
    token = reveal(tenant.get("instagram_access_token"))
    account_id = tenant.get("instagram_account_id")
    if not token or not account_id:
        return None, None
    now = datetime.now(timezone.utc)
    expires = _as_utc(tenant.get("instagram_token_expires_at"))
    issued = _as_utc(tenant.get("instagram_token_issued_at")) or now
    if db is not None and expires and expires - now < RENEW_WITHIN and now - issued > RENEW_MIN_AGE:
        try:
            renewed = await refresh_token(token)
            token = renewed["access_token"]
            await db["tenants"].update_one({"tenant_id": tenant["tenant_id"]}, {"$set": {
                "instagram_access_token": protect(token),
                "instagram_token_issued_at": now,
                "instagram_token_expires_at": now + timedelta(seconds=int(renewed.get("expires_in") or 5184000)),
            }})
        except Exception as e:
            logger.warning(f"Instagram token for {tenant.get('tenant_id')} not renewed: {e}")
    return token, account_id


async def send_text_to(tenant: Dict[str, Any], contact: str, text: str, db=None) -> SendResult:
    if is_instagram(contact):
        token, account_id = await instagram_credentials(tenant, db)
        return await send_dm(token, account_id, igsid_of(contact), text)
    token, phone_number_id = resolve_tenant_whatsapp_credentials(tenant)
    return await send_text(to_phone=contact, text=text, token=token, phone_number_id=phone_number_id)


async def send_buttons_to(tenant: Dict[str, Any], contact: str, body: str, buttons: List[Dict[str, str]], db=None) -> SendResult:
    """Buttons on WhatsApp, quick replies on Instagram. Either way the tap comes back with the button's id."""
    if is_instagram(contact):
        token, account_id = await instagram_credentials(tenant, db)
        return await send_quick_replies(token, account_id, igsid_of(contact), body, buttons)
    token, phone_number_id = resolve_tenant_whatsapp_credentials(tenant)
    return await send_buttons(to_phone=contact, body=body, buttons=buttons, token=token, phone_number_id=phone_number_id)
