"""Instagram DMs: connecting an account, the webhook, sending replies in the right app,
and the agent's Instagram rules.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

import asyncio
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

import api.v1.endpoints.instagram as instagram_endpoint
import services.channels as channels
import services.instagram as instagram
from agents.customer_support.prompt import compile_customer_support_prompt
from core import instagram_utils
from core.database import get_database
from core.settings import settings
from core.whatsapp_utils import SendResult
from fake_mongo import FakeCollection, FakeDB
from main import app


def run(coro):
    return asyncio.run(coro)


def dm(text=None, sender="555", account="17841", mid="m1", **message):
    msg = {"mid": mid, **message}
    if text is not None:
        msg["text"] = text
    return {"object": "instagram", "entry": [{"id": account, "messaging": [
        {"sender": {"id": sender}, "recipient": {"id": account}, "timestamp": 1, "message": msg}
    ]}]}


# ------------------------------------------------------------------ parsing

def test_text_taps_and_voice_notes_are_read():
    assert [(e.contact, e.kind, e.text) for e in instagram.parse_events(dm("salam"))] == [("ig:555", "text", "salam")]
    tap = instagram.parse_events(dm("Confirm", quick_reply={"payload": "order_confirm:ORD-1"}))[0]
    assert (tap.kind, tap.payload) == ("tap", "order_confirm:ORD-1")
    voice = instagram.parse_events(dm(attachments=[{"type": "audio", "payload": {"url": "https://cdn/x.mp4"}}]))[0]
    assert (voice.kind, voice.url) == ("audio", "https://cdn/x.mp4")
    photo = instagram.parse_events(dm(attachments=[{"type": "image", "payload": {"url": "https://cdn/x.jpg"}}]))[0]
    assert photo.kind == "unsupported"


def test_our_own_messages_and_receipts_are_skipped():
    assert instagram.parse_events(dm("hi", is_echo=True)) == []
    assert instagram.parse_events(dm("hi", sender="17841")) == []
    read = {"entry": [{"id": "17841", "messaging": [{"sender": {"id": "555"}, "read": {"mid": "m0"}}]}]}
    assert instagram.parse_events(read) == []


def test_signature_check(monkeypatch):
    monkeypatch.setattr(settings, "INSTAGRAM_APP_SECRET", "s3cret")
    body = b'{"entry": []}'
    good = "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    assert instagram_utils.signature_ok(body, good)
    assert not instagram_utils.signature_ok(body, "sha256=00")
    assert not instagram_utils.signature_ok(body, None)


# ------------------------------------------------------------------ webhook

@pytest.fixture
def webhook(monkeypatch):
    db = FakeDB()
    db["tenants"].docs.append({"tenant_id": "t1", "instagram_account_id": "17841"})
    db["processed_messages"] = FakeCollection(unique=["message_id"])
    app.dependency_overrides[get_database] = lambda: db
    monkeypatch.setattr(settings, "INSTAGRAM_APP_SECRET", "")
    handled = []

    async def fake_handle(_db, tenant, event, request_id="bg"):
        handled.append((tenant["tenant_id"], event.contact, event.text))

    monkeypatch.setattr(instagram_endpoint, "handle_instagram_event", fake_handle)
    yield TestClient(app), db, handled
    app.dependency_overrides.clear()


def test_a_dm_reaches_the_business_that_owns_the_account(webhook):
    client, _, handled = webhook
    assert client.post("/api/v1/instagram/webhook", json=dm("price?")).json() == {"status": "success"}
    assert handled == [("t1", "ig:555", "price?")]


def test_a_retried_dm_is_handled_once(webhook):
    client, _, handled = webhook
    client.post("/api/v1/instagram/webhook", json=dm("price?"))
    client.post("/api/v1/instagram/webhook", json=dm("price?"))
    assert len(handled) == 1


def test_a_dm_for_an_unknown_account_is_ignored(webhook):
    client, _, handled = webhook
    client.post("/api/v1/instagram/webhook", json=dm("hi", account="999"))
    assert handled == []


def test_a_badly_signed_webhook_is_refused(webhook, monkeypatch):
    client, _, handled = webhook
    monkeypatch.setattr(settings, "INSTAGRAM_APP_SECRET", "s3cret")
    response = client.post("/api/v1/instagram/webhook", content=json.dumps(dm("hi")),
                           headers={"x-hub-signature-256": "sha256=bad", "content-type": "application/json"})
    assert response.status_code == 403 and handled == []


def test_webhook_verification(webhook):
    client, _, _ = webhook
    ok = client.get("/api/v1/instagram/webhook", params={"hub.mode": "subscribe", "hub.verify_token": settings.WHATSAPP_VERIFY_TOKEN, "hub.challenge": "42"})
    assert ok.text == "42"
    assert client.get("/api/v1/instagram/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "no", "hub.challenge": "42"}).status_code == 403


# ------------------------------------------------------------- sending replies

def test_replies_go_out_in_the_app_the_customer_used(monkeypatch):
    sent = []

    async def ig(token, account, igsid, text):
        sent.append(("instagram", account, igsid, text))
        return SendResult(ok=True)

    async def wa(to_phone, text, token=None, phone_number_id=None):
        sent.append(("whatsapp", phone_number_id, to_phone, text))
        return SendResult(ok=True)

    monkeypatch.setattr(channels, "send_dm", ig)
    monkeypatch.setattr(channels, "send_text", wa)
    monkeypatch.setattr(channels, "reveal", lambda v: v)
    monkeypatch.setattr(channels, "resolve_tenant_whatsapp_credentials", lambda t: ("wa-token", "pn1"))
    tenant = {"tenant_id": "t1", "instagram_access_token": "ig-token", "instagram_account_id": "17841"}
    run(channels.send_text_to(tenant, "ig:555", "hi"))
    run(channels.send_text_to(tenant, "923001111111", "hi"))
    assert sent == [("instagram", "17841", "555", "hi"), ("whatsapp", "pn1", "923001111111", "hi")]


def test_buttons_become_quick_replies_on_instagram(monkeypatch):
    got = {}

    async def quick(token, account, igsid, text, buttons):
        got.update(igsid=igsid, buttons=buttons)
        return SendResult(ok=True)

    monkeypatch.setattr(channels, "send_quick_replies", quick)
    monkeypatch.setattr(channels, "reveal", lambda v: v)
    tenant = {"tenant_id": "t1", "instagram_access_token": "tok", "instagram_account_id": "17841"}
    run(channels.send_buttons_to(tenant, "ig:555", "Confirm?", [{"id": "order_confirm:ORD-1", "title": "Confirm"}]))
    assert got == {"igsid": "555", "buttons": [{"id": "order_confirm:ORD-1", "title": "Confirm"}]}


def test_a_token_close_to_expiry_is_renewed(monkeypatch):
    from datetime import datetime, timedelta, timezone

    db = FakeDB()
    now = datetime.now(timezone.utc)
    tenant = {"tenant_id": "t1", "instagram_access_token": "old", "instagram_account_id": "17841",
              "instagram_token_issued_at": now - timedelta(days=55), "instagram_token_expires_at": now + timedelta(days=5)}
    db["tenants"].docs.append(dict(tenant))

    async def refresh(token):
        return {"access_token": "new", "expires_in": 5184000}

    monkeypatch.setattr(channels, "refresh_token", refresh)
    monkeypatch.setattr(channels, "reveal", lambda v: v)
    monkeypatch.setattr(channels, "protect", lambda v: f"enc:{v}")
    token, _ = run(channels.instagram_credentials(tenant, db))
    assert token == "new"
    assert db["tenants"].docs[0]["instagram_access_token"] == "enc:new"


def test_long_dms_are_split_at_instagrams_limit(monkeypatch):
    parts = []

    async def fake_send(token, account, payload):
        parts.append(payload["message"]["text"])
        return SendResult(ok=True)

    monkeypatch.setattr(instagram_utils, "_send", fake_send)
    run(instagram_utils.send_dm("tok", "17841", "555", "x" * 2500))
    assert [len(p) for p in parts] == [1000, 1000, 500]


# ------------------------------------------------------------------ connecting

def test_connect_state_is_signed_and_expires():
    state = instagram.make_state("t1", "u1")
    assert instagram.read_state(state) == {"tenant_id": "t1", "user_id": "u1"}
    with pytest.raises(ValueError, match="expired"):
        instagram.read_state(state + "x")


@pytest.fixture
def meta_login(monkeypatch):
    async def exchange(code):
        return {"access_token": "short", "user_id": 1}

    async def long_lived(token):
        return {"access_token": "long", "expires_in": 5184000}

    async def profile(token):
        return {"user_id": "17841", "username": "glowstudio"}

    subscribed = []

    async def subscribe(token):
        subscribed.append(token)

    monkeypatch.setattr(instagram, "exchange_code", exchange)
    monkeypatch.setattr(instagram, "long_lived_token", long_lived)
    monkeypatch.setattr(instagram, "account_profile", profile)
    monkeypatch.setattr(instagram, "subscribe_account", subscribe)
    monkeypatch.setattr(instagram, "protect", lambda v: f"enc:{v}")
    return subscribed


def test_connecting_saves_the_account_and_subscribes_it(meta_login):
    db = FakeDB()
    db["tenants"].docs.append({"tenant_id": "t1"})
    run(instagram.connect_account(db, "t1", "code"))
    t = db["tenants"].docs[0]
    assert (t["instagram_account_id"], t["instagram_username"], t["instagram_access_token"]) == ("17841", "glowstudio", "enc:long")
    assert t["instagram_connected"] is True and meta_login == ["long"]


def test_an_account_already_used_by_another_business_is_refused(meta_login):
    db = FakeDB()
    db["tenants"].docs += [{"tenant_id": "t1"}, {"tenant_id": "t2", "instagram_account_id": "17841"}]
    with pytest.raises(ValueError, match="another business"):
        run(instagram.connect_account(db, "t1", "code"))
    assert meta_login == []


def test_the_callback_sends_the_owner_back_to_settings(meta_login, monkeypatch):
    db = FakeDB()
    db["tenants"].docs.append({"tenant_id": "t1"})
    app.dependency_overrides[get_database] = lambda: db
    try:
        client = TestClient(app)
        ok = client.get("/api/v1/instagram/callback", params={"code": "c", "state": instagram.make_state("t1", "u1")}, follow_redirects=False)
        bad = client.get("/api/v1/instagram/callback", params={"code": "c", "state": "forged"}, follow_redirects=False)
    finally:
        app.dependency_overrides.clear()
    assert ok.status_code == 302 and ok.headers["location"].endswith("/dashboard/settings?instagram=connected")
    assert "instagram_error=" in bad.headers["location"]


# ------------------------------------------------------------------- the agent

def test_prompt_on_instagram_asks_for_a_phone_and_skips_forms():
    tenant = {"business_name": "Glow", "forms": []}
    prompt = compile_customer_support_prompt(tenant, "", channel="instagram")
    assert "talking to customers on Instagram" in prompt
    assert "`contact_phone`" in prompt
    assert "INSTAGRAM:" not in compile_customer_support_prompt(tenant, "")
