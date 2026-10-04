"""Billing part 2: the payment provider, invoices and month arithmetic.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

import asyncio
from datetime import datetime, timezone

import pytest

from core import settings as settings_module
from services import invoices as invoices_module
from services.billing import add_months
from services.invoices import pay_open_invoice, plan_fee_pkr
from services.payments import get_payment_provider
from services.payments.base import PaymentResult
from services.payments.dummy import DummyPaymentProvider


def test_add_months_keeps_the_day_and_clamps_short_months():
    assert add_months(datetime(2026, 1, 15, tzinfo=timezone.utc), 1) == datetime(2026, 2, 15, tzinfo=timezone.utc)
    assert add_months(datetime(2026, 1, 31, tzinfo=timezone.utc), 1) == datetime(2026, 2, 28, tzinfo=timezone.utc)
    assert add_months(datetime(2026, 10, 3, tzinfo=timezone.utc), 12) == datetime(2027, 10, 3, tzinfo=timezone.utc)


def test_fee_follows_the_interval():
    assert plan_fee_pkr("basic", "month") == 2999
    assert plan_fee_pkr("basic", "year") == 29990
    assert plan_fee_pkr("pro", "year") == 119990


def test_dummy_provider_always_succeeds_with_a_dummy_reference(monkeypatch):
    async def no_wait(_seconds):
        return None

    monkeypatch.setattr("services.payments.dummy.asyncio.sleep", no_wait)
    result = asyncio.run(DummyPaymentProvider().pay_invoice({"invoice_id": "INV-1"}, "card"))
    assert result.ok
    assert result.reference.startswith("DUMMY-")


def test_unknown_payments_provider_is_refused(monkeypatch):
    monkeypatch.setattr(settings_module.settings, "PAYMENTS_PROVIDER", "stripe")
    with pytest.raises(RuntimeError):
        get_payment_provider()


class _NoRows:
    async def find_one(self, *_, **__):
        return None


class EmptyDB(dict):
    """A failed payment only looks up the owner to email them, so an empty database is enough."""
    def __getitem__(self, name):
        return _NoRows()


def test_failed_payment_leaves_the_invoice_open(monkeypatch):
    class FailingProvider:
        name = "failing"

        async def pay_invoice(self, invoice, method):
            return PaymentResult(ok=False, error="Card declined.")

    monkeypatch.setattr(invoices_module, "get_payment_provider", lambda: FailingProvider())
    paid, error = asyncio.run(pay_open_invoice(EmptyDB(), {"invoice_id": "INV-2026-000001", "tenant_id": "t1"}))
    assert paid is None
    assert error == "Card declined."
