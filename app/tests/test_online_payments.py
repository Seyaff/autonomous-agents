"""Online order payments: button ids, expiry, and what a provider callback may and may not change.
The providers are faked, since their real signature formats aren't built yet.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

import asyncio
import copy
from datetime import datetime, timedelta, timezone

import pytest
from pymongo.errors import DuplicateKeyError

from services import online_payments as op


class FakeCollection:
    def __init__(self, docs=None, unique=None):
        self.docs = docs or []
        self.unique = unique or []

    def _match(self, doc, query):
        return all(doc.get(k) == v for k, v in query.items())

    async def find_one(self, query=None, *_, **__):
        for d in self.docs:
            if self._match(d, query or {}):
                return copy.deepcopy(d)
        return None

    async def update_one(self, query, update):
        for d in self.docs:
            if self._match(d, query):
                d.update(update.get("$set", {}))
                for k, v in update.get("$push", {}).items():
                    d.setdefault(k, []).append(v)
                return

    async def insert_one(self, doc):
        for keys in self.unique:
            for d in self.docs:
                if all(d.get(k) == doc.get(k) for k in keys):
                    raise DuplicateKeyError("duplicate")
        self.docs.append(copy.deepcopy(doc))


class FakeDB(dict):
    pass


def make_db(order):
    db = FakeDB()
    db["orders"] = FakeCollection([order])
    db["tenants"] = FakeCollection([{"tenant_id": "t1", "business_name": "Diner"}])
    db[op.PAYMENTS] = FakeCollection(unique=[("provider", "reference")])
    return db


def order(**extra):
    base = {
        "order_id": "ORD-1", "tenant_id": "t1", "customer_phone": "923001234567",
        "total_amount": 1350.0, "status": op.AWAITING_PAYMENT, "payment_reference": "REF-1",
        "payment_expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
        "status_history": [], "currency": "PKR", "eta_minutes": 30,
    }
    return {**base, **extra}


class FakeProvider:
    name = "easypaisa"

    def __init__(self, event=None, error=None):
        self.event = event
        self.error = error

    def configured(self):
        return True

    def verify_webhook(self, headers, body):
        if self.error:
            raise self.error
        return self.event


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    """No WhatsApp or live order events during these tests."""
    sent = []

    async def fake_reply(tenant, phone, text):
        sent.append(text)

    async def fake_buttons(tenant, phone, body, buttons):
        sent.append(body)

    async def fake_broadcast(**_):
        return None

    monkeypatch.setattr(op, "_reply", fake_reply)
    monkeypatch.setattr(op, "_buttons", fake_buttons)
    monkeypatch.setattr("core.events.broadcast_order_update", fake_broadcast)
    return sent


def run(coro):
    return asyncio.run(coro)


def test_pay_button_ids_round_trip():
    assert op.parse_pay_button("order_pay:ORD-1A2B:easypaisa") == ("ORD-1A2B", "easypaisa")
    assert op.parse_pay_button("order_pay:ORD-1A2B:cod") == ("ORD-1A2B", "cod")
    assert op.parse_pay_button("order_confirm:ORD-1") == (None, None)


def test_a_link_is_expired_only_after_its_deadline():
    now = datetime.now(timezone.utc)
    assert not op.expired({"payment_expires_at": now + timedelta(minutes=1)}, now)
    assert op.expired({"payment_expires_at": now - timedelta(seconds=1)}, now)
    assert not op.expired({}, now)


def test_a_signed_paid_callback_marks_the_order_paid(monkeypatch):
    db = make_db(order())
    monkeypatch.setitem(op.PROVIDERS, "easypaisa", FakeProvider({"reference": "REF-1", "amount_pkr": 1350, "status": "paid"}))
    assert run(op.handle_payment_webhook(db, "easypaisa", {}, b"{}")) == "marked paid"
    saved = db["orders"].docs[0]
    assert saved["status"] == "pending"
    assert saved["paid_at"] is not None


def test_a_callback_for_the_wrong_amount_changes_nothing(monkeypatch):
    db = make_db(order())
    monkeypatch.setitem(op.PROVIDERS, "easypaisa", FakeProvider({"reference": "REF-1", "amount_pkr": 1, "status": "paid"}))
    assert run(op.handle_payment_webhook(db, "easypaisa", {}, b"{}")) == "amount mismatch"
    assert db["orders"].docs[0]["status"] == op.AWAITING_PAYMENT


def test_a_repeated_callback_is_recorded_once(monkeypatch):
    db = make_db(order())
    monkeypatch.setitem(op.PROVIDERS, "easypaisa", FakeProvider({"reference": "REF-1", "amount_pkr": 1350, "status": "paid"}))
    assert run(op.handle_payment_webhook(db, "easypaisa", {}, b"{}")) == "marked paid"
    assert run(op.handle_payment_webhook(db, "easypaisa", {}, b"{}")) == "already recorded"
    assert len(db[op.PAYMENTS].docs) == 1


def test_an_unsigned_callback_is_refused_and_changes_nothing(monkeypatch):
    db = make_db(order())
    monkeypatch.setitem(op.PROVIDERS, "easypaisa", FakeProvider(error=ValueError("bad signature")))
    with pytest.raises(ValueError):
        run(op.handle_payment_webhook(db, "easypaisa", {}, b"{}"))
    assert db["orders"].docs[0]["status"] == op.AWAITING_PAYMENT


def test_a_callback_for_an_order_no_longer_waiting_is_ignored(monkeypatch):
    db = make_db(order(status="pending"))
    monkeypatch.setitem(op.PROVIDERS, "easypaisa", FakeProvider({"reference": "REF-1", "amount_pkr": 1350, "status": "paid"}))
    assert run(op.handle_payment_webhook(db, "easypaisa", {}, b"{}")).startswith("ignored")


def test_cash_on_delivery_sends_the_order_to_the_kitchen():
    db = make_db(order(status=op.CHOOSING_PAYMENT))
    assert run(op.handle_payment_choice(db, {"tenant_id": "t1"}, "923001234567", "ORD-1", "cod")) == "cod"
    saved = db["orders"].docs[0]
    assert saved["status"] == "pending"
    assert saved["payment_method"] == "cod"


def test_an_unconfigured_provider_offers_cash_instead_of_a_link():
    db = make_db(order(status=op.CHOOSING_PAYMENT))
    assert run(op.handle_payment_choice(db, {"tenant_id": "t1"}, "923001234567", "ORD-1", "jazzcash")) == "provider unavailable"
    assert db["orders"].docs[0]["status"] == op.CHOOSING_PAYMENT


def test_no_provider_is_offered_before_setup():
    assert op.provider_for({"online_payment_provider": "easypaisa"}) is None
    assert op.provider_for({}) is None
