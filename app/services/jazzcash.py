"""
JazzCash hosted checkout (page redirection): building the signed form, and checking the signature
on what JazzCash sends back.

Working from JazzCash's hosted-checkout format. The sandbox is the test: if a field or the signature
is wrong, JazzCash refuses it with an error code, and that is what we fix against.
"""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple
from urllib.parse import parse_qsl
from zoneinfo import ZoneInfo

from core.settings import settings

KARACHI = ZoneInfo("Asia/Karachi")
SUCCESS_CODE = "000"
# Codes JazzCash uses for a payment that is still being processed. Nothing is marked paid yet.
PENDING_CODES = ("124", "157")


def txn_ref(order_id: str, now: datetime) -> str:
    """JazzCash wants an alphanumeric reference. Keep it unique per attempt, and matchable to the order.
    The time part is Karachi time, like every other JazzCash timestamp."""
    local = now.astimezone(KARACHI)
    return f"T{order_id.replace('-', '')}{local.strftime('%H%M%S')}"


def signed_fields(fields: Dict[str, str], salt: str) -> Dict[str, str]:
    """Adds pp_SecureHash to a set of pp_ fields."""
    out = dict(fields)
    out["pp_SecureHash"] = secure_hash(out, salt)
    return out


def secure_hash(fields: Dict[str, str], salt: str) -> str:
    """HMAC-SHA256 over the salt and the sorted, non-empty pp_ values (pp_SecureHash itself excluded)."""
    items: List[Tuple[str, str]] = sorted(
        (k, str(v)) for k, v in fields.items()
        if k.startswith("pp_") and k != "pp_SecureHash" and v not in ("", None)
    )
    message = salt + "&" + "&".join(v for _, v in items)
    return hmac.new(salt.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest().upper()


def payment_fields(*, reference: str, amount_pkr: int, description: str, return_url: str, now: datetime) -> Dict[str, str]:
    """The fields JazzCash expects for a hosted payment. Amount is in paisa, as JazzCash requires."""
    local = now.astimezone(KARACHI)
    expiry = (now + timedelta(minutes=15)).astimezone(KARACHI)
    return {
        "pp_Version": "1.1",
        "pp_TxnType": settings.JAZZCASH_TXN_TYPE,
        "pp_Language": "EN",
        "pp_MerchantID": settings.JAZZCASH_MERCHANT_ID,
        "pp_Password": settings.JAZZCASH_PASSWORD,
        "pp_TxnRefNo": reference,
        "pp_Amount": str(int(amount_pkr) * 100),
        "pp_TxnCurrency": "PKR",
        "pp_TxnDateTime": local.strftime("%Y%m%d%H%M%S"),
        "pp_TxnExpiryDateTime": expiry.strftime("%Y%m%d%H%M%S"),
        "pp_BillReference": reference,
        "pp_Description": description[:200],
        "pp_ReturnURL": return_url,
    }


def auto_submit_form(fields: Dict[str, str], action: str) -> str:
    """An HTML page that posts the signed fields to JazzCash straight away."""
    from html import escape

    inputs = "".join(f'<input type="hidden" name="{escape(k)}" value="{escape(v)}">' for k, v in fields.items())
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>Payment</title></head>"
        f"<body><p>Payment ke page par ja rahe hain...</p><form id='pay' method='post' action='{escape(action)}'>{inputs}</form>"
        "<script>document.getElementById('pay').submit();</script></body></html>"
    )


def parse_callback(body: bytes) -> Dict[str, str]:
    """JazzCash posts back form fields. Returns them as a dict."""
    return dict(parse_qsl(body.decode("utf-8", errors="replace"), keep_blank_values=True))


def verify_callback(fields: Dict[str, str], salt: str) -> None:
    """Raises if the signature on a JazzCash callback doesn't match what we'd sign."""
    received = (fields.get("pp_SecureHash") or "").upper()
    if not received or not hmac.compare_digest(received, secure_hash(fields, salt)):
        raise ValueError("JazzCash signature doesn't match.")
