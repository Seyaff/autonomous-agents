"""Payment callbacks from JazzCash and Easypaisa. Each one is checked against its signature."""

import logging

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from core.database import get_database
from core.settings import settings
from services import jazzcash
from services.online_payments import AWAITING_PAYMENT, ProviderNotConfigured, expired, handle_payment_webhook

logger = logging.getLogger(__name__)

payments_router = APIRouter(prefix="/payments", tags=["Payments"])


@payments_router.get("/jazzcash/checkout/{reference}", response_class=HTMLResponse)
async def jazzcash_checkout(reference: str):
    """The page the customer opens from WhatsApp. It posts the signed payment form to JazzCash."""
    db = get_database()
    order = await db["orders"].find_one({"payment_reference": reference})
    if not order or order.get("status") != AWAITING_PAYMENT or expired(order):
        raise HTTPException(status_code=404, detail="This payment link isn't active.")
    now = datetime.now(timezone.utc)
    fields = jazzcash.signed_fields(
        jazzcash.payment_fields(
            reference=reference,
            amount_pkr=int(round(float(order.get("total_amount", 0)))),
            description=f"Order {order['order_id']}",
            return_url=settings.PAYMENT_RETURN_URL or f"{settings.PUBLIC_API_BASE.rstrip('/')}/payments/jazzcash/return",
            now=now,
        ),
        settings.JAZZCASH_INTEGRITY_SALT,
    )
    return HTMLResponse(jazzcash.auto_submit_form(fields, settings.JAZZCASH_CHECKOUT_URL))


@payments_router.post("/jazzcash/return")
async def jazzcash_return(request: Request):
    """Where JazzCash sends the customer back. The signature decides what happened, not the page."""
    body = await request.body()
    frontend = settings.frontend_origin
    try:
        outcome = await handle_payment_webhook(get_database(), "jazzcash", {}, body)
    except Exception as e:
        logger.warning(f"[payments] JazzCash return refused: {e}")
        return RedirectResponse(url=f"{frontend}/dashboard?payment=failed", status_code=303)
    logger.info(f"[payments] JazzCash return: {outcome}")
    result = "ok" if outcome == "marked paid" else "failed"
    return RedirectResponse(url=f"{frontend}/dashboard?payment={result}", status_code=303)


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
