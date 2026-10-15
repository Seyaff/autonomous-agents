"""WhatsApp templates and broadcast campaigns: the template rules, sending, opt-outs,
delivery receipts, and the webhook that carries receipts and review results.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import api.v1.endpoints.whatsapp as whatsapp_endpoint
import services.campaigns as campaigns
import services.templates as templates
from core.database import get_database
from core.whatsapp_utils import SendResult
from fake_mongo import FakeDB
from main import app
from services.campaigns import Audience, CampaignCreate, ParamSource
from services.templates import TemplateButton, TemplateDraft


def run(coro):
    return asyncio.run(coro)


# ------------------------------------------------------------ template rules

def draft(**overrides):
    base = {
        "name": "Eid Offer",
        "category": "MARKETING",
        "language": "en",
        "body": "Hi {{1}}, Eid Mubarak! Get {{2}} off this week at our store.",
        "body_examples": ["Sana", "20%"],
    }
    base.update(overrides)
    return TemplateDraft(**base)


def test_template_name_is_made_safe_for_meta():
    assert draft().name == "eid_offer"
    with pytest.raises(ValidationError, match="lowercase letters"):
        draft(name="Eid! Offer")


def test_variables_must_be_numbered_in_order():
    with pytest.raises(ValidationError, match="in order"):
        draft(body="Hi {{2}}, get {{1}} off today.", body_examples=["a", "b"])


def test_a_variable_cannot_start_or_end_the_message():
    with pytest.raises(ValidationError, match="start or end"):
        draft(body="{{1}}, welcome to our shop.", body_examples=["Sana"])
    with pytest.raises(ValidationError, match="start or end"):
        draft(body="Your discount code is {{1}}.", body_examples=["EID20"])


def test_every_variable_needs_an_example():
    with pytest.raises(ValidationError, match="example for each"):
        draft(body_examples=["Sana"])


def test_header_takes_at_most_one_variable_and_needs_an_example():
    with pytest.raises(ValidationError, match="at most one"):
        draft(header_text="{{1}} and {{2}}", header_example="x")
    with pytest.raises(ValidationError, match="header variable"):
        draft(header_text="Hello {{1}}")


def test_buttons_are_checked():
    with pytest.raises(ValidationError, match="https://"):
        TemplateButton(type="URL", text="Shop", url="http://example.com")
    with pytest.raises(ValidationError, match="country code"):
        TemplateButton(type="PHONE_NUMBER", text="Call", phone_number="12")


def test_components_are_in_metas_format_with_quick_replies_first():
    d = draft(
        header_text="Eid sale",
        footer="Reply STOP to opt out",
        buttons=[
            {"type": "URL", "text": "Shop now", "url": "https://shop.example.com"},
            {"type": "QUICK_REPLY", "text": "Stop promotions"},
        ],
    )
    components = templates.build_components(d)
    assert [c["type"] for c in components] == ["HEADER", "BODY", "FOOTER", "BUTTONS"]
    assert components[1]["example"] == {"body_text": [["Sana", "20%"]]}
    assert [b["type"] for b in components[3]["buttons"]] == ["QUICK_REPLY", "URL"]


def test_standard_order_update_template_passes_the_rules():
    d = templates.order_update_draft()
    assert d.category == "UTILITY"
    assert len(d.body_examples) == 4


# ---------------------------------------------------------- stored templates

META_TEMPLATE = {
    "id": "991",
    "name": "eid_offer",
    "language": "en",
    "status": "APPROVED",
    "category": "MARKETING",
    "components": [
        {"type": "HEADER", "format": "TEXT", "text": "Eid sale"},
        {"type": "BODY", "text": "Hi {{1}}, get {{2}} off this week at our store."},
        {"type": "FOOTER", "text": "Reply STOP to opt out"},
        {"type": "BUTTONS", "buttons": [{"type": "QUICK_REPLY", "text": "Stop promotions"}]},
    ],
}


def test_stored_template_knows_how_many_values_it_needs():
    doc = templates.stored_template("t1", META_TEMPLATE)
    assert doc["body_variables"] == 2 and doc["header_variables"] == 0
    assert doc["status"] == "APPROVED"


def test_render_shows_what_the_customer_reads():
    doc = templates.stored_template("t1", META_TEMPLATE)
    text = templates.render(doc, ["Sana", "20%"])
    assert "*Eid sale*" in text
    assert "Hi Sana, get 20% off this week" in text
    assert "[Stop promotions]" in text


def test_send_components_check_the_count_and_clean_values():
    doc = templates.stored_template("t1", META_TEMPLATE)
    with pytest.raises(ValueError, match="needs 2"):
        templates.send_components(doc, ["only one"], [])
    components = templates.send_components(doc, ["Sana\nKhan", "20%     off"], [])
    values = [p["text"] for p in components[0]["parameters"]]
    assert values == ["Sana Khan", "20%   off"]


def test_only_approved_text_templates_can_be_sent():
    assert templates.sendable(None)[0] is False
    pending = templates.stored_template("t1", {**META_TEMPLATE, "status": "PENDING"})
    assert "isn't approved" in templates.sendable(pending)[1]
    image = templates.stored_template("t1", {**META_TEMPLATE, "components": [{"type": "HEADER", "format": "IMAGE"}, {"type": "BODY", "text": "Hi"}]})
    assert "picture or file" in templates.sendable(image)[1]


def test_review_result_from_the_webhook_updates_the_template():
    db = FakeDB()
    db["tenants"].docs.append({"tenant_id": "t1", "whatsapp_business_id": "waba1"})
    run(db["wa_templates"].insert_one(templates.stored_template("t1", {**META_TEMPLATE, "status": "PENDING"})))
    changed = run(templates.apply_status_update(db, "waba1", {"event": "REJECTED", "message_template_id": 991, "reason": "INVALID_FORMAT"}))
    assert changed
    row = db["wa_templates"].docs[0]
    assert row["status"] == "REJECTED" and row["rejected_reason"] == "INVALID_FORMAT"


# ------------------------------------------------------------------ campaigns

def test_phone_numbers_are_normalized():
    assert campaigns.normalize_phone("+92 300 1234567") == "923001234567"
    assert campaigns.normalize_phone("0092-300-1234567") == "923001234567"
    assert campaigns.normalize_phone("123") is None


def test_customer_name_values_use_the_first_name_or_a_fallback():
    sources = [ParamSource(kind="customer_name"), ParamSource(kind="text", value="20%")]
    assert campaigns.fill(sources, "Sana Khan") == ["Sana", "20%"]
    assert campaigns.fill(sources, "") == ["there", "20%"]


def test_stop_and_start():
    db = FakeDB()
    tenant = {"tenant_id": "t1", "business_name": "Glow"}
    assert "won't get promotional" in run(campaigns.handle_marketing_keywords(db, tenant, "923001", "STOP"))
    assert db["marketing_opt_outs"].docs[0]["phone"] == "923001"
    # "start" from someone who never opted out is an ordinary message for the agent.
    assert run(campaigns.handle_marketing_keywords(db, tenant, "923002", "start")) is None
    assert "again" in run(campaigns.handle_marketing_keywords(db, tenant, "923001", "Start"))
    assert db["marketing_opt_outs"].docs == []


def audience_db():
    db = FakeDB()
    now = datetime.now(timezone.utc)
    db["conversations"].docs += [
        {"tenant_id": "t1", "customer_phone": "923001111111", "customer_name": "Sana"},
        {"tenant_id": "t1", "customer_phone": "923002222222", "customer_name": "Ali"},
        {"tenant_id": "t1", "customer_phone": "923003333333", "customer_name": "Opted"},
        {"tenant_id": "t2", "customer_phone": "923009999999", "customer_name": "Other business"},
    ]
    db["orders"].docs += [
        {"tenant_id": "t1", "customer_phone": "923001111111", "created_at": now - timedelta(days=3), "status": "delivered"},
        {"tenant_id": "t1", "customer_phone": "923002222222", "created_at": now - timedelta(days=60), "status": "delivered"},
    ]
    db["marketing_opt_outs"].docs.append({"tenant_id": "t1", "phone": "923003333333"})
    return db


def test_audience_all_skips_opted_out_and_other_businesses():
    recipients, skipped = run(campaigns.resolve_audience(audience_db(), "t1", Audience(kind="all")))
    assert [r["phone"] for r in recipients] == ["923001111111", "923002222222"]
    assert skipped == 1


def test_audience_by_recent_orders():
    recipients, _ = run(campaigns.resolve_audience(audience_db(), "t1", Audience(kind="ordered_within_days", days=30)))
    assert [r["phone"] for r in recipients] == ["923001111111"]
    assert recipients[0]["name"] == "Sana"


def test_audience_from_a_pasted_list():
    recipients, skipped = run(campaigns.resolve_audience(
        audience_db(), "t1", Audience(kind="phones", phones=["+92 300 2222222", "923003333333", "bad"])
    ))
    assert [r["phone"] for r in recipients] == ["923002222222"]
    assert skipped == 1


def campaign_db():
    db = audience_db()
    db["wa_templates"].docs.append(templates.stored_template("t1", META_TEMPLATE))
    return db


TENANT = {"tenant_id": "t1", "business_name": "Glow", "phone_number_id": "pn1"}


def payload(**overrides):
    base = {
        "name": "Eid blast",
        "template_name": "eid_offer",
        "language": "en",
        "body_params": [{"kind": "customer_name"}, {"kind": "text", "value": "20%"}],
        "audience": {"kind": "all"},
    }
    base.update(overrides)
    return CampaignCreate(**base)


def test_campaign_needs_a_value_for_every_variable():
    with pytest.raises(ValueError, match="needs 2"):
        run(campaigns.create_campaign(campaign_db(), TENANT, payload(body_params=[{"kind": "customer_name"}]), "u1"))


def test_campaign_sends_to_each_recipient_and_counts_receipts(monkeypatch):
    db = campaign_db()
    sent = []

    async def fake_send(db_, tenant, phone, doc, body, header=None, sender="human"):
        sent.append((phone, body))
        return SendResult(ok=True, status=200, message_id=f"wamid.{phone}"), None

    monkeypatch.setattr(campaigns, "send_template_message", fake_send)
    campaign = run(campaigns.create_campaign(db, TENANT, payload(), "u1"))
    assert campaign["counts"]["total"] == 2 and campaign["counts"]["skipped_opted_out"] == 1

    assert run(campaigns.run_campaign(db, TENANT, campaign["campaign_id"], gap=0)) == "done"
    assert sent == [("923001111111", ["Sana", "20%"]), ("923002222222", ["Ali", "20%"])]

    run(campaigns.record_receipt(db, "wamid.923001111111", "delivered"))
    run(campaigns.record_receipt(db, "wamid.923001111111", "read"))
    run(campaigns.record_receipt(db, "wamid.923001111111", "delivered"))  # late, out of order: ignored
    run(campaigns.record_receipt(db, "wamid.923002222222", "read"))      # read without delivered counts both
    counts = db["campaigns"].docs[0]["counts"]
    assert (counts["sent"], counts["delivered"], counts["read"], counts["failed"]) == (2, 2, 2, 0)
    assert db["campaigns"].docs[0]["status"] == "done"


def test_a_token_failure_pauses_the_campaign_without_losing_recipients(monkeypatch):
    db = campaign_db()

    async def refused(*_a, **_k):
        return SendResult(ok=False, status=401, error_message="bad token"), None

    async def no_alert(*_a, **_k):
        return None

    monkeypatch.setattr(campaigns, "send_template_message", refused)
    monkeypatch.setattr("services.alerts.raise_alert", no_alert)
    campaign = run(campaigns.create_campaign(db, TENANT, payload(), "u1"))
    assert run(campaigns.run_campaign(db, TENANT, campaign["campaign_id"], gap=0)) == "paused"
    assert all(r["status"] == "queued" for r in db["campaign_recipients"].docs)
    assert db["campaigns"].docs[0]["counts"]["failed"] == 0


def test_a_failed_receipt_is_counted_once():
    db = FakeDB()
    db["campaigns"].docs.append({"campaign_id": "c1", "counts": {"delivered": 0, "read": 0, "failed": 0}})
    db["campaign_recipients"].docs.append({"_id": 1, "campaign_id": "c1", "wamid": "w1", "status": "sent"})
    run(campaigns.record_receipt(db, "w1", "failed", {"title": "Number not on WhatsApp"}))
    run(campaigns.record_receipt(db, "w1", "failed", {"title": "Number not on WhatsApp"}))
    assert db["campaigns"].docs[0]["counts"]["failed"] == 1
    assert db["campaign_recipients"].docs[0]["error"] == "Number not on WhatsApp"


# ------------------------------------------------------------------- webhook

@pytest.fixture
def webhook(monkeypatch):
    db = FakeDB()
    db["tenants"].docs.append({"tenant_id": "t1", "phone_number_id": "pn1", "whatsapp_business_id": "waba1"})
    app.dependency_overrides[get_database] = lambda: db
    calls = {"receipts": [], "texts": []}

    async def fake_receipts(_db, statuses):
        calls["receipts"].extend(statuses)

    async def fake_text_turn(**kwargs):
        calls["texts"].append(kwargs)

    monkeypatch.setattr(whatsapp_endpoint, "_handle_receipts", fake_receipts)
    monkeypatch.setattr(whatsapp_endpoint, "handle_text_turn", fake_text_turn)
    yield TestClient(app), db, calls
    app.dependency_overrides.clear()


def change(field, value):
    return {"object": "whatsapp_business_account", "entry": [{"id": "waba1", "changes": [{"field": field, "value": value}]}]}


def test_receipts_reach_the_receipt_handler(webhook):
    client, _, calls = webhook
    body = change("messages", {"metadata": {"phone_number_id": "pn1"}, "statuses": [{"id": "w1", "status": "read", "timestamp": "1700000000"}]})
    assert client.post("/api/v1/whatsapp", json=body).json() == {"status": "success"}
    assert calls["receipts"] == [{"id": "w1", "status": "read", "timestamp": "1700000000"}]


def test_template_review_results_update_the_template(webhook):
    client, db, _ = webhook
    db["wa_templates"].docs.append({"tenant_id": "t1", "meta_id": "991", "name": "eid_offer", "language": "en", "status": "PENDING"})
    client.post("/api/v1/whatsapp", json=change("message_template_status_update", {"event": "APPROVED", "message_template_id": 991}))
    assert db["wa_templates"].docs[0]["status"] == "APPROVED"


def test_a_template_button_tap_is_handled_like_text(webhook):
    client, _, calls = webhook
    body = change("messages", {
        "metadata": {"phone_number_id": "pn1"},
        "contacts": [{"profile": {"name": "Sana"}}],
        "messages": [{"id": "wamid.in1", "from": "923001111111", "type": "button", "button": {"text": "Stop promotions", "payload": "STOP"}}],
    })
    client.post("/api/v1/whatsapp", json=body)
    assert calls["texts"][0]["user_payload"] == "Stop promotions"
    assert calls["texts"][0]["wamid"] == "wamid.in1"
