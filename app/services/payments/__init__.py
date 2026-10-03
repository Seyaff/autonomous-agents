"""Payment providers. Only the dummy provider exists for now, chosen by PAYMENTS_PROVIDER."""

from core.settings import settings
from services.payments.base import PaymentProvider, PaymentResult
from services.payments.dummy import DummyPaymentProvider

__all__ = ["PaymentProvider", "PaymentResult", "get_payment_provider"]


def get_payment_provider() -> PaymentProvider:
    name = (settings.PAYMENTS_PROVIDER or "dummy").lower()
    if name == "dummy":
        return DummyPaymentProvider()
    raise RuntimeError(f"Unknown payments provider: {name}")
