"""Google sign-in callback: a brand-new Google user gets an account and is signed in.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

import copy
import types

import pytest
from fastapi.testclient import TestClient

import api.v1.endpoints.auth as auth_module
from core.database import get_database
from main import app


class FakeCollection:
    def __init__(self):
        self.docs = []

    async def find_one(self, query=None, *_, **__):
        for d in self.docs:
            if all(d.get(k) == v for k, v in (query or {}).items()):
                return copy.deepcopy(d)
        return None

    async def insert_one(self, doc):
        self.docs.append(copy.deepcopy(doc))

    async def update_one(self, query, update):
        for d in self.docs:
            if all(d.get(k) == v for k, v in query.items()):
                d.update(update.get("$set", {}))


class FakeDB(dict):
    def __getattr__(self, name):
        return self[name]


def fake_oauth(userinfo):
    async def authorize_access_token(request):
        return {"userinfo": userinfo}

    return types.SimpleNamespace(google=types.SimpleNamespace(authorize_access_token=authorize_access_token))


@pytest.fixture
def db():
    fake = FakeDB()
    fake["users"] = FakeCollection()
    app.dependency_overrides[get_database] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


def test_new_google_user_is_created_and_signed_in(db, monkeypatch):
    monkeypatch.setattr(auth_module, "oauth", fake_oauth({"sub": "g-123", "email": "Owner@Example.com", "name": "Ali"}))
    client = TestClient(app, follow_redirects=False)

    r = client.get("/api/v1/auth/google/callback?state=/setup")

    assert r.status_code in (302, 307)
    assert r.headers["location"].endswith("/setup")
    assert "access_token" in r.headers.get("set-cookie", "")
    user = db["users"].docs[0]
    assert user["email"] == "owner@example.com"
    assert user["google_id"] == "g-123"
    assert user["is_onboarded"] is False


def test_returning_google_user_is_signed_in_without_a_duplicate(db, monkeypatch):
    db["users"].docs.append({"user_id": "usr_existing", "google_id": "g-9", "email": "a@b.com", "is_onboarded": True})
    monkeypatch.setattr(auth_module, "oauth", fake_oauth({"sub": "g-9", "email": "a@b.com"}))
    client = TestClient(app, follow_redirects=False)

    r = client.get("/api/v1/auth/google/callback?state=/dashboard")

    assert r.status_code in (302, 307)
    assert len(db["users"].docs) == 1
    assert "access_token" in r.headers.get("set-cookie", "")
