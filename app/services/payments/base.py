"""
The payment provider interface. A real gateway implements this and replaces the dummy
provider without touching plans, invoices or screens.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol


@dataclass
class PaymentResult:
    ok: bool
    reference: str = ""
    error: Optional[str] = None


class PaymentProvider(Protocol):
    name: str

    async def pay_invoice(self, invoice: Dict[str, Any], method: str) -> PaymentResult: ...
