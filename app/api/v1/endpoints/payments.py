"""Payment callbacks from JazzCash and Easypaisa. Each one is checked against its signature."""

import logging

from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from core.database import get_database
from core.settings import settings
from services import jazzcash
from services.online_payments import AWAITING_PAYMENT, ProviderNotConfigured, expired, handle_payment_webhook

# Outcomes from handle_payment_webhook that mean the money has been received.
# "already recorded" is a repeated callback for a payment that was already marked paid.
PAID_OUTCOMES = {"marked paid", "invoice paid", "already recorded"}

logger = logging.getLogger(__name__)

payments_router = APIRouter(prefix="/payments", tags=["Payments"])


@payments_router.get("/jazzcash/checkout/{reference}", response_class=HTMLResponse)
async def jazzcash_checkout(reference: str):
    """The page the owner or customer opens. It posts the signed payment form to JazzCash."""
    from services.invoices import INVOICES

    db = get_database()
    now = datetime.now(timezone.utc)
    return_url = settings.PAYMENT_RETURN_URL or f"{settings.PUBLIC_API_BASE.rstrip('/')}/payments/jazzcash/return"

    order = await db["orders"].find_one({"payment_reference": reference})
    if order:
        if order.get("status") != AWAITING_PAYMENT or expired(order):
            raise HTTPException(status_code=404, detail="This payment link isn't active.")
        amount, description = int(round(float(order.get("total_amount", 0)))), f"Order {order['order_id']}"
    else:
        invoice = await db[INVOICES].find_one({"payment_reference": reference})
        if not invoice or invoice.get("status") != "open":
            raise HTTPException(status_code=404, detail="This payment link isn't active.")
        amount, description = int(round(float(invoice.get("amount_pkr", 0)))), f"Invoice {invoice['invoice_id']}"

    fields = jazzcash.signed_fields(
        jazzcash.payment_fields(reference=reference, amount_pkr=amount, description=description, return_url=return_url, now=now),
        settings.JAZZCASH_INTEGRITY_SALT,
    )
    return HTMLResponse(jazzcash.auto_submit_form(fields, settings.JAZZCASH_CHECKOUT_URL))


@payments_router.post("/jazzcash/return")
async def jazzcash_return(request: Request):
    """Where JazzCash sends the customer back. The signature decides what happened, not the page."""
    body = await request.body()
    frontend = settings.frontend_origin
    fields = jazzcash.parse_callback(body)
    code = fields.get("pp_ResponseCode", "")
    message = fields.get("pp_ResponseMessage", "")
    try:
        outcome = await handle_payment_webhook(get_database(), "jazzcash", {}, body)
    except Exception as e:
        logger.warning(f"[payments] JazzCash return refused: {e}")
        return _dashboard_redirect(frontend, "failed", code, "The payment could not be verified.")
    logger.info(f"[payments] JazzCash return: {outcome} (code {code})")
    if outcome in PAID_OUTCOMES:
        return _dashboard_redirect(frontend, "ok", code, message)
    if outcome == "payment pending":
        return _dashboard_redirect(frontend, "pending", code, message)
    return _dashboard_redirect(frontend, "failed", code, message)


def _dashboard_redirect(frontend: str, result: str, code: str, message: str) -> RedirectResponse:
    """Sends the customer back to the dashboard with the result. The message is shown to them, so no secrets go here."""
    query = urlencode({"payment": result, "code": code, "message": message})
    return RedirectResponse(url=f"{frontend}/dashboard?{query}", status_code=303)


@payments_router.post("/webhook/{provider}")
async def payment_webhook(provider: str, request: Request):
    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    try:
        outcome = await handle_payment_webhook(get_database(), provider, headers, body)
    except ProviderNotConfigured:
        raise HTTPException(status_code=503, detail="This payment provider isn't set up yet.")
    except Exception as e:
        # A bad signature or a malformed callback. Nothing is changed.
        logger.warning(f"[payments] callback from {provider} refused: {e}")
        raise HTTPException(status_code=400, detail="Callback not accepted.")
    logger.info(f"[payments] {provider} callback: {outcome}")
    return {"status": "received", "outcome": outcome}
