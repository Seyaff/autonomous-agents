"""Payment callbacks from JazzCash and Easypaisa. Each one is checked against its signature."""

import logging

from fastapi import APIRouter, HTTPException, Request

from core.database import get_database
from services.online_payments import ProviderNotConfigured, handle_payment_webhook

logger = logging.getLogger(__name__)

payments_router = APIRouter(prefix="/payments", tags=["Payments"])


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
