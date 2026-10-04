"""Billing edge cases at the HTTP layer: declined payments, wrong states, and other people's invoices.

These run against an in-memory database and fake payment results, so a declined card can be
simulated. The dummy provider never declines, so it can't test this on its own.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

import asyncio
import copy

import pytest
from fastapi.testclient import TestClient

import api.v1.endpoints.billing as billing_endpoints
from core.database import get_database
from main import app
from middlewares.auth_middleware import require_owner


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    def _match(self, doc, query):
        return all(doc.get(k) == v for k, v in query.items())

    async def find_one(self, query=None, projection=None, **_):
        for d in self.docs:
            if self._match(d, query or {}):
                return copy.deepcopy(d)
        return None

    async def insert_one(self, doc):
        self.docs.append(copy.deepcopy(doc))

    async def update_one(self, query, update):
        for d in self.docs:
            if self._match(d, query):
                for k, v in update.get("$set", {}).items():
                    _set_path(d, k, v)
                return


def _set_path(doc, dotted, value):
    parts = dotted.split(".")
    cur = doc
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


class FakeDB(dict):
    pass


def owner_db(subscription, invoices=None):
    db = FakeDB()
    db["tenants"] = FakeCollection([{"tenant_id": "t1", "timezone": "UTC", "subscription": subscription}])
    db["invoices"] = FakeCollection(invoices or [])
    db["usage_counters"] = FakeCollection([])
    db["counters"] = FakeCollection([])
    return db


@pytest.fixture
def client():
    app.dependency_overrides[require_owner] = lambda: {"active_tenant_id": "t1", "role": "OWNER"}
    yield TestClient(app)
    app.dependency_overrides.clear()


def use_db(db):
    app.dependency_overrides[get_database] = lambda: db


def active_sub():
    return {"plan": "standard", "interval": "month", "status": "active", "cancel_at_period_end": False,
            "pending_plan": None, "current_period_start": "2026-10-01T00:00:00+00:00",
            "current_period_end": "2026-11-01T00:00:00+00:00"}


def trialing_sub():
    return {"plan": "basic", "interval": "month", "status": "trialing", "cancel_at_period_end": False,
            "trial_ends_at": "2099-01-01T00:00:00+00:00"}


def open_invoice(invoice_id="INV-2026-000001", tenant_id="t1"):
    return {"invoice_id": invoice_id, "tenant_id": tenant_id, "purpose": "renewal", "plan_key": "standard",
            "interval": "month", "amount_pkr": 5999, "status": "open", "lines": [], "period_start": None,
            "period_end": None, "due_at": "2099-01-01T00:00:00+00:00", "created_at": "2026-10-01T00:00:00+00:00"}


def fake_pay(ok: bool, error: str = "Card declined."):
    async def pay(db, invoice, method="card"):
        if ok:
            return None, None
        return None, error
    return pay


def test_declined_checkout_returns_402_and_leaves_the_invoice_open(client, monkeypatch):
    db = owner_db(trialing_sub())
    use_db(db)

    async def fake_create(db_, tenant_id, plan, interval, now=None):
        inv = open_invoice("INV-2026-000009", tenant_id)
        db_["invoices"].docs.append(inv)
        return inv

    async def declined(db, invoice, method="card"):
        return None, "Card declined."

    monkeypatch.setattr(billing_endpoints, "create_subscription_invoice", fake_create)
    monkeypatch.setattr(billing_endpoints, "pay_open_invoice", declined)

    r = client.post("/api/v1/billing/checkout", json={"plan": "standard", "interval": "month"})
    assert r.status_code == 402
    assert r.json()["detail"] == "Card declined."
    assert r.json()["invoice_id"] == "INV-2026-000009"
    # The plan didn't start.
    assert db["tenants"].docs[0]["subscription"]["status"] == "trialing"


def test_declined_payment_of_an_open_invoice_returns_402(client, monkeypatch):
    db = owner_db(active_sub(), [open_invoice()])
    use_db(db)
    monkeypatch.setattr(billing_endpoints, "pay_open_invoice", fake_pay(False, "Insufficient funds."))

    r = client.post("/api/v1/billing/invoices/INV-2026-000001/pay", json={"method": "card"})
    assert r.status_code == 402
    assert r.json()["detail"] == "Insufficient funds."
    assert db["invoices"].docs[0]["status"] == "open"


def test_paying_an_invoice_that_is_already_paid_is_refused(client):
    paid = {**open_invoice(), "status": "paid"}
    use_db(owner_db(active_sub(), [paid]))
    r = client.post("/api/v1/billing/invoices/INV-2026-000001/pay", json={})
    assert r.status_code == 409


def test_paying_someone_elses_invoice_is_not_found(client):
    other = open_invoice(tenant_id="someone_else")
    use_db(owner_db(active_sub(), [other]))
    r = client.post("/api/v1/billing/invoices/INV-2026-000001/pay", json={})
    assert r.status_code == 404


def test_checkout_is_refused_while_a_plan_is_active(client):
    use_db(owner_db(active_sub()))
    r = client.post("/api/v1/billing/checkout", json={"plan": "pro", "interval": "month"})
    assert r.status_code == 409


def test_plan_change_is_refused_during_the_trial(client):
    use_db(owner_db(trialing_sub()))
    r = client.post("/api/v1/billing/change-plan", json={"plan": "pro"})
    assert r.status_code == 409


def test_changing_to_the_same_plan_is_refused(client):
    use_db(owner_db(active_sub()))
    r = client.post("/api/v1/billing/change-plan", json={"plan": "standard"})
    assert r.status_code == 409


def test_cancel_is_refused_during_the_trial(client):
    use_db(owner_db(trialing_sub()))
    r = client.post("/api/v1/billing/cancel")
    assert r.status_code == 409


def test_keep_plan_is_refused_when_nothing_is_cancelled(client):
    use_db(owner_db(active_sub()))
    r = client.post("/api/v1/billing/resume")
    assert r.status_code == 409


def test_cancel_then_keep_restores_renewal(client):
    db = owner_db(active_sub())
    use_db(db)
    assert client.post("/api/v1/billing/cancel").status_code == 200
    assert db["tenants"].docs[0]["subscription"]["cancel_at_period_end"] is True
    assert client.post("/api/v1/billing/resume").status_code == 200
    assert db["tenants"].docs[0]["subscription"]["cancel_at_period_end"] is False


def test_downgrade_is_scheduled_not_charged(client):
    db = owner_db(active_sub())
    use_db(db)
    r = client.post("/api/v1/billing/change-plan", json={"plan": "basic"})
    assert r.status_code == 200
    assert r.json()["invoice"] is None
    assert db["tenants"].docs[0]["subscription"]["pending_plan"] == "basic"
    assert db["tenants"].docs[0]["subscription"]["plan"] == "standard"


def test_declined_upgrade_leaves_the_plan_unchanged(client, monkeypatch):
    db = owner_db(active_sub())
    use_db(db)

    async def create_up(db_, tenant_id, subscription, target, now):
        inv = open_invoice("INV-2026-000005", tenant_id)
        db_["invoices"].docs.append(inv)
        return inv

    monkeypatch.setattr(billing_endpoints, "create_upgrade_invoice", create_up)
    monkeypatch.setattr(billing_endpoints, "pay_open_invoice", fake_pay(False, "Card declined."))
    r = client.post("/api/v1/billing/change-plan", json={"plan": "pro"})
    assert r.status_code == 402
    assert db["tenants"].docs[0]["subscription"]["plan"] == "standard"


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    app.dependency_overrides.clear()
