"""Email: what is sent, that nothing is sent without a key, that each event sends once, and that a
broken email never breaks the request that caused it.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

import asyncio

import pytest
from pymongo.errors import DuplicateKeyError

from core.settings import settings
from services import email as mail


class FakeLog:
    def __init__(self):
        self.keys = set()

    async def insert_one(self, doc):
        if doc["key"] in self.keys:
            raise DuplicateKeyError("duplicate key")
        self.keys.add(doc["key"])

    async def delete_one(self, query):
        self.keys.discard(query["key"])


class FakeDB(dict):
    pass


class FakeResponse:
    status_code = 200
    text = ""


@pytest.fixture
def resend(monkeypatch):
    """Turns email on with a fake key, and records what would have been sent."""
    sent = []
    db = FakeDB()
    db["email_log"] = FakeLog()

    async def fake_post(self, url, headers=None, json=None):
        sent.append(json)
        return FakeResponse()

    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_key")
    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    monkeypatch.setattr("core.database.get_database", lambda: db)
    return sent, db


def test_render_escapes_the_text_and_links_the_button():
    html, text = mail.render("Hi <script>", ["Line & more"], "Open", "/dashboard")
    assert "&lt;script&gt;" in html
    assert "Line &amp; more" in html
    assert "https://" in html or "http://" in html
    assert "Open:" in text


def test_nothing_is_sent_without_a_key(monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "")
    assert asyncio.run(mail.send("owner@example.com", "Hi", "<p>x</p>", "x")) is False


def test_an_email_goes_out_once_per_event(resend):
    sent, _ = resend
    first = asyncio.run(mail.send("owner@example.com", "Welcome", "<p>a</p>", "a", dedupe_key="welcome:usr_1"))
    second = asyncio.run(mail.send("owner@example.com", "Welcome", "<p>a</p>", "a", dedupe_key="welcome:usr_1"))
    assert first is True
    assert second is False
    assert len(sent) == 1


def test_a_failed_send_frees_its_key_so_it_can_be_retried(resend, monkeypatch):
    _, db = resend

    class Refused(FakeResponse):
        status_code = 500

    async def refuse(self, url, headers=None, json=None):
        return Refused()

    monkeypatch.setattr("httpx.AsyncClient.post", refuse)
    assert asyncio.run(mail.send("o@example.com", "x", "<p/>", "x", dedupe_key="k1")) is False
    assert "k1" not in db["email_log"].keys


def test_a_broken_email_is_logged_not_raised(monkeypatch):
    # A missing field would break the text. The event must still return normally.
    assert mail.invoice_created("o@example.com", {"business_name": "x"}, {"invoice_id": "INV-1"}) is None


def test_payment_received_mentions_the_amount_and_the_end_date(resend, monkeypatch):
    sent_later = []
    monkeypatch.setattr(mail, "send_later", lambda *a, **k: sent_later.append((a, k)))
    mail.payment_received("o@example.com", {"business_name": "Diner"},
                          {"invoice_id": "INV-2026-000007", "amount_pkr": 5999}, "2026-11-03")
    (args, kwargs), = sent_later
    assert "5,999" in args[3]
    assert "03 Nov 2026" in args[3]
    assert args[4] == "payment_received:INV-2026-000007"
