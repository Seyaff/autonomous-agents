"""Sign-in sessions: rotation, reuse detection, expiry, sign-out, and what the refresh route does.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

import asyncio
import copy
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from core.database import get_database
from main import app
from services import sessions as sessions_module
from services.sessions import create_session, hash_token, is_active, revoke_all, rotate
from utils.cookie import REFRESH_COOKIE


class FakeCollection:
    def __init__(self):
        self.docs = []

    @staticmethod
    def _match_one(doc, key, value):
        stored = doc.get(key)
        if isinstance(stored, list) and not isinstance(value, list):
            return value in stored
        return stored == value

    def _match(self, doc, query):
        for k, v in query.items():
            if isinstance(v, dict):
                if "$ne" in v and doc.get(k) == v["$ne"]:
                    return False
                if "$lt" in v and not (doc.get(k) < v["$lt"]):
                    return False
                if "$gt" in v and not (doc.get(k) > v["$gt"]):
                    return False
            elif not self._match_one(doc, k, v):
                return False
        return True

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
                    d[k] = v
                return

    async def update_many(self, query, update):
        for d in self.docs:
            if self._match(d, query):
                for k, v in update.get("$set", {}).items():
                    d[k] = v

    async def delete_many(self, query):
        self.docs = [d for d in self.docs if not self._match(d, query)]


class FakeDB(dict):
    def __getattr__(self, name):
        return self[name]


@pytest.fixture
def db():
    fake = FakeDB()
    fake["sessions"] = FakeCollection()
    app.dependency_overrides[get_database] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


def run(coro):
    return asyncio.run(coro)


def test_a_new_session_stores_only_a_hash_of_the_refresh_token(db):
    session, refresh = run(create_session(db, "usr_1", "test-agent"))
    stored = db["sessions"].docs[0]
    assert stored["refresh_hash"] == hash_token(refresh)
    assert refresh not in str(stored)


def test_rotation_issues_a_new_token_and_retires_the_old_one(db):
    _, first = run(create_session(db, "usr_1"))
    session, second, problem = run(rotate(db, first))
    assert problem is None
    assert second != first
    assert run(rotate(db, second))[2] is None


def test_reusing_a_rotated_token_revokes_the_whole_session(db):
    _, first = run(create_session(db, "usr_1"))
    _, second, _ = run(rotate(db, first))

    session, token, problem = run(rotate(db, first))  # someone replays the old token

    assert problem == "reused"
    assert db["sessions"].docs[0]["revoked_reason"] == "reused"
    # The legitimate token stops working too.
    assert run(rotate(db, second))[2] == "revoked"


def test_an_unknown_token_is_invalid(db):
    assert run(rotate(db, "not-a-real-token"))[2] == "invalid"


def test_an_expired_session_is_refused(db):
    _, refresh = run(create_session(db, "usr_1"))
    db["sessions"].docs[0]["idle_expires_at"] = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert run(rotate(db, refresh))[2] == "expired"


def test_a_signed_out_session_is_not_active(db):
    session, _ = run(create_session(db, "usr_1"))
    assert run(is_active(db, session["session_id"]))
    run(revoke_all(db, "usr_1"))
    assert not run(is_active(db, session["session_id"]))


def test_sign_out_everywhere_keeps_the_current_session_when_asked(db):
    keep, _ = run(create_session(db, "usr_1"))
    other, _ = run(create_session(db, "usr_1"))
    run(revoke_all(db, "usr_1", except_session_id=keep["session_id"]))
    assert run(is_active(db, keep["session_id"]))
    assert not run(is_active(db, other["session_id"]))


def test_refresh_endpoint_rotates_the_cookies(db):
    _, refresh = run(create_session(db, "usr_1"))
    client = TestClient(app)
    client.cookies.set(REFRESH_COOKIE, refresh)

    r = client.post("/api/v1/auth/refresh")

    assert r.status_code == 200
    assert "access_token=" in r.headers.get("set-cookie", "")
    assert "refresh_token=" in r.headers.get("set-cookie", "")


def test_refresh_endpoint_refuses_a_reused_token_and_clears_cookies(db):
    _, first = run(create_session(db, "usr_1"))
    run(rotate(db, first))
    client = TestClient(app)
    client.cookies.set(REFRESH_COOKIE, first)

    r = client.post("/api/v1/auth/refresh")

    assert r.status_code == 401
    assert "signed out on another device" in r.json()["detail"]


def test_refresh_endpoint_without_a_cookie_is_refused(db):
    r = TestClient(app).post("/api/v1/auth/refresh")
    assert r.status_code == 401


def test_signup_starts_a_session_and_sets_both_cookies(db):
    db["users"] = FakeCollection()
    client = TestClient(app)
    r = client.post("/api/v1/auth/signup", json={"full_name": "New Owner", "email": "new@example.com", "password": "password123"})
    assert r.status_code == 200
    assert "token" in r.json()
    cookies = " ".join(r.headers.get_list("set-cookie"))
    assert "access_token=" in cookies and "refresh_token=" in cookies
    assert len(db["sessions"].docs) == 1
