"""Connecting a restaurant's WhatsApp number by hand. The same checks apply as the Meta popup.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

import copy

import pytest
from fastapi.testclient import TestClient

import api.v1.endpoints.tenant as tenant_endpoints
from core.database import get_database
from main import app
from middlewares.auth_middleware import require_owner

GOOD_TOKEN = "EAAGm0PX4ZCpsBA" + "x" * 40


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    def _match(self, doc, query):
        for k, v in query.items():
            if isinstance(v, dict) and "$ne" in v:
                if doc.get(k) == v["$ne"]:
                    return False
            elif doc.get(k) != v:
                return False
        return True

    async def find_one(self, query=None, projection=None, **_):
        for d in self.docs:
            if self._match(d, query or {}):
                return copy.deepcopy(d)
        return None

    async def update_one(self, query, update):
        for d in self.docs:
            if self._match(d, query):
                d.update(update.get("$set", {}))


class FakeDB(dict):
    # The endpoints use both db.tenants and db["tenants"].
    def __getattr__(self, name):
        return self[name]


@pytest.fixture
def db():
    fake = FakeDB()
    fake["tenants"] = FakeCollection([{"tenant_id": "t1", "business_name": "Diner"}])
    app.dependency_overrides[get_database] = lambda: fake
    app.dependency_overrides[require_owner] = lambda: {"active_tenant_id": "t1", "role": "OWNER"}
    yield fake
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


def body(**overrides):
    return {"phone_number_id": "123456789012345", "waba_id": "987654321098765", "access_token": GOOD_TOKEN, **overrides}


def test_non_numeric_ids_are_refused_and_recorded(client, db):
    r = client.post("/api/v1/tenant/whatsapp/manual", json=body(phone_number_id="not-a-number"))
    assert r.status_code == 400
    assert db["tenants"].docs[0]["whatsapp_status"] == "error"
    assert "whatsapp_access_token" not in db["tenants"].docs[0]


def test_a_token_meta_rejects_is_not_saved(client, db, monkeypatch):
    async def rejected(token, phone_number_id):
        raise ValueError("Meta: the access token has expired.")

    monkeypatch.setattr(tenant_endpoints, "verify_phone_number", rejected)
    r = client.post("/api/v1/tenant/whatsapp/manual", json=body())
    assert r.status_code == 400
    assert r.json()["detail"] == "Meta: the access token has expired."
    assert db["tenants"].docs[0]["whatsapp_status"] == "error"
    assert "whatsapp_access_token" not in db["tenants"].docs[0]


def test_a_valid_token_connects_and_is_stored_encrypted(client, db, monkeypatch):
    async def verified(token, phone_number_id):
        return {"display_phone_number": "+92 300 0000000", "verified_name": "Diner"}

    async def subscribed(token, waba_id):
        return None

    stored = []

    def fake_protect(value):
        stored.append(value)
        return "enc:v1:" + "x"

    monkeypatch.setattr(tenant_endpoints, "verify_phone_number", verified)
    monkeypatch.setattr(tenant_endpoints, "subscribe_business_account", subscribed)
    monkeypatch.setattr(tenant_endpoints, "protect", fake_protect)

    r = client.post("/api/v1/tenant/whatsapp/manual", json=body())
    assert r.status_code == 200
    tenant = db["tenants"].docs[0]
    assert tenant["whatsapp_status"] == "connected"
    assert tenant["phone_number_id"] == "123456789012345"
    assert tenant["whatsapp_access_token"] == "enc:v1:x"
    assert stored == [GOOD_TOKEN]


def test_a_number_used_by_another_restaurant_is_refused(client, db, monkeypatch):
    db["tenants"].docs.append({"tenant_id": "t2", "phone_number_id": "123456789012345"})

    async def verified(token, phone_number_id):
        return {}

    monkeypatch.setattr(tenant_endpoints, "verify_phone_number", verified)
    r = client.post("/api/v1/tenant/whatsapp/manual", json=body())
    assert r.status_code == 409
    assert db["tenants"].docs[0]["whatsapp_status"] == "error"
