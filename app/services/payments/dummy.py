"""
The dummy payment provider. Nothing is charged and no external service is called.
The app shows "Test payment, no money is charged" while this provider is active.
"""

import asyncio
import secrets
from typing import Any, Dict

from services.payments.base import PaymentResult


class DummyPaymentProvider:
    name = "dummy"

    async def pay_invoice(self, invoice: Dict[str, Any], method: str) -> PaymentResult:
        await asyncio.sleep(1.0)
        return PaymentResult(ok=True, reference=f"DUMMY-{secrets.token_hex(4).upper()}")
