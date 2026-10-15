"""Owner-built forms sent as WhatsApp Flows: the layout rules, the Flow JSON, publishing,
the customer's answers, and the agent's send_form tool.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import agents.customer_support.tools as tools
import api.v1.endpoints.whatsapp as whatsapp_endpoint
import services.forms as forms
from agents.customer_support.prompt import compile_customer_support_prompt
from core.database import get_database
from core.whatsapp_utils import SendResult
from fake_mongo import FakeDB
from main import app
from services.forms import FormDraft


def run(coro):
    return asyncio.run(coro)


def booking_form(**overrides):
    base = {
        "name": "Booking request",
        "purpose": "When a customer wants an appointment",
        "screens": [
            {"title": "Your details", "fields": [
                {"label": "Full name", "kind": "short_text"},
                {"label": "Phone", "kind": "phone", "required": False},
            ]},
            {"title": "Appointment", "fields": [
                {"label": "Service", "kind": "dropdown", "options": ["Haircut", "Facial"]},
                {"label": "Date", "kind": "date"},
                {"label": "Extras", "kind": "checkboxes", "options": ["Wash", "Blow dry"], "required": False},
                {"label": "I agree to the cancellation policy", "kind": "opt_in"},
            ]},
        ],
    }
    base.update(overrides)
    return FormDraft(**base)


# ---------------------------------------------------------------- the layout

def test_field_names_come_from_labels_and_are_unique():
    d = booking_form(screens=[{"title": "A", "fields": [
        {"label": "Full name"}, {"label": "Full name!"}, {"label": "2nd phone", "kind": "phone"},
    ]}])
    assert [f.name for f in d.screens[0].fields] == ["full_name", "full_name_2", "f_2nd_phone"]


def test_meta_label_limits_are_enforced():
    with pytest.raises(ValidationError, match="20 characters"):
        booking_form(screens=[{"title": "A", "fields": [{"label": "What is your full legal name", "kind": "short_text"}]}])
    # Radio and checkbox groups allow longer labels than text inputs.
    booking_form(screens=[{"title": "A", "fields": [{"label": "Which service would you like", "kind": "choice", "options": ["A"]}]}])


def test_option_fields_need_distinct_options():
    with pytest.raises(ValidationError, match="at least one option"):
        booking_form(screens=[{"title": "A", "fields": [{"label": "Service", "kind": "dropdown"}]}])
    with pytest.raises(ValidationError, match="same option twice"):
        booking_form(screens=[{"title": "A", "fields": [{"label": "Service", "kind": "choice", "options": ["Cut", "cut"]}]}])


def test_flow_json_navigates_then_completes_with_every_answer():
    flow = forms.build_flow_json(booking_form())
    first, last = flow["screens"]
    assert flow["version"] == forms.FLOW_JSON_VERSION
    assert (first["id"], last["id"]) == ("STEP_A", "STEP_B")
    assert "terminal" not in first and last["terminal"] is True

    first_footer = first["layout"]["children"][-1]
    assert first_footer["on-click-action"]["name"] == "navigate"
    assert first_footer["on-click-action"]["next"] == {"type": "screen", "name": "STEP_B"}

    payload = last["layout"]["children"][-1]["on-click-action"]["payload"]
    assert payload["full_name"] == "${screen.STEP_A.form.full_name}"
    assert payload["service"] == "${form.service}"
    assert set(payload) == {"full_name", "phone", "service", "date", "extras", "i_agree_to_the_cancellation_policy"}


def test_components_map_to_metas_types():
    children = forms.build_flow_json(booking_form())["screens"][1]["layout"]["children"]
    by_name = {c.get("name"): c for c in children}
    assert by_name["service"]["type"] == "Dropdown"
    assert by_name["service"]["data-source"] == [{"id": "opt_0", "title": "Haircut"}, {"id": "opt_1", "title": "Facial"}]
    assert by_name["date"]["type"] == "DatePicker"
    assert by_name["extras"]["type"] == "CheckboxGroup"
    assert by_name["i_agree_to_the_cancellation_policy"]["type"] == "OptIn"


# ---------------------------------------------------------------- publishing

TENANT = {"tenant_id": "t1", "business_name": "Glow", "whatsapp_business_id": "waba1", "phone_number_id": "pn1"}


@pytest.fixture
def meta(monkeypatch):
    calls = {"created": [], "uploaded": [], "published": [], "retired": [], "errors": []}
    monkeypatch.setattr(forms, "resolve_tenant_whatsapp_credentials", lambda t: ("token", "pn1"))

    async def create(token, waba, name, categories):
        calls["created"].append(name)
        return f"flow{len(calls['created'])}"

    async def upload(token, flow_id, flow_json):
        calls["uploaded"].append(flow_id)
        return calls["errors"].pop(0) if calls["errors"] else []

    async def publish(token, flow_id):
        calls["published"].append(flow_id)

    async def retire(token, flow_id, published):
        calls["retired"].append((flow_id, published))

    monkeypatch.setattr(forms, "create_flow", create)
    monkeypatch.setattr(forms, "upload_flow_json", upload)
    monkeypatch.setattr(forms, "publish_flow", publish)
    monkeypatch.setattr(forms, "retire_flow", retire)
    return calls


def test_publish_creates_uploads_and_publishes(meta):
    db = FakeDB()
    doc = run(forms.save_form(db, "t1", booking_form()))
    published = run(forms.publish_form(db, TENANT, doc["form_id"]))
    assert meta["created"] == ["Booking request v1"]
    assert meta["published"] == ["flow1"]
    assert published["meta_status"] == "PUBLISHED" and published["has_unpublished_changes"] is False


def test_validation_errors_are_shown_and_the_draft_flow_is_reused(meta):
    db = FakeDB()
    doc = run(forms.save_form(db, "t1", booking_form()))
    meta["errors"].append(["INVALID_PROPERTY: label too long (screens/0)"])
    with pytest.raises(ValueError, match="label too long"):
        run(forms.publish_form(db, TENANT, doc["form_id"]))
    assert db["wa_forms"].docs[0]["status"] == "error"
    run(forms.publish_form(db, TENANT, doc["form_id"]))
    assert meta["created"] == ["Booking request v1"]  # the same draft Flow, not a second one
    assert meta["uploaded"] == ["flow1", "flow1"]


def test_editing_a_published_form_makes_a_new_flow_and_retires_the_old(meta):
    db = FakeDB()
    doc = run(forms.save_form(db, "t1", booking_form()))
    run(forms.publish_form(db, TENANT, doc["form_id"]))

    # Only the message text changed: nothing to publish again.
    saved = run(forms.save_form(db, "t1", booking_form(body="Fill this in please"), doc["form_id"]))
    assert saved["has_unpublished_changes"] is False

    edited = booking_form(screens=[{"title": "Quick", "fields": [{"label": "Full name"}]}])
    saved = run(forms.save_form(db, "t1", edited, doc["form_id"]))
    assert saved["has_unpublished_changes"] is True
    republished = run(forms.publish_form(db, TENANT, doc["form_id"]))
    assert meta["created"] == ["Booking request v1", "Booking request v2"]
    assert meta["retired"] == [("flow1", True)]
    assert republished["meta_flow_id"] == "flow2" and republished["version"] == 2


# ---------------------------------------------------------- the answers back

def published_db(meta):
    db = FakeDB()
    doc = run(forms.save_form(db, "t1", booking_form()))
    run(forms.publish_form(db, TENANT, doc["form_id"]))
    return db, db["wa_forms"].docs[0]


def test_answers_are_saved_with_labels_and_option_titles(meta, monkeypatch):
    db, form = published_db(meta)

    async def sent(**kwargs):
        return SendResult(ok=True, message_id="wamid.form")

    monkeypatch.setattr(forms, "send_flow", sent)
    run(forms.send_form_to(db, TENANT, "923001111111", form))
    flow_token = db["wa_form_sends"].docs[0]["flow_token"]

    answers = json.dumps({
        "flow_token": flow_token, "full_name": "Sana Khan", "service": "opt_1", "date": "2026-10-20",
        "extras": ["opt_0", "opt_1"], "i_agree_to_the_cancellation_policy": True,
    })
    saved = run(forms.record_response(db, "t1", "923001111111", answers, "wamid.reply"))
    assert saved["answers"] == [
        {"label": "Full name", "value": "Sana Khan"},
        {"label": "Service", "value": "Facial"},
        {"label": "Date", "value": "2026-10-20"},
        {"label": "Extras", "value": "Wash, Blow dry"},
        {"label": "I agree to the cancellation policy", "value": "Yes"},
    ]
    assert db["wa_forms"].docs[0]["responses"] == 1
    text = forms.response_message(saved)
    assert text.startswith("[form submitted: Booking request]") and "Service: Facial" in text


def test_an_unknown_form_reply_is_ignored(meta):
    db = FakeDB()
    assert run(forms.record_response(db, "t1", "923001111111", json.dumps({"flow_token": "nope"}), None)) is None


# ------------------------------------------------------------- agent and webhook

def test_prompt_lists_published_forms_with_their_purpose():
    tenant = {"business_name": "Glow", "forms": [{"name": "Booking request", "purpose": "When a customer wants an appointment"}]}
    prompt = compile_customer_support_prompt(tenant, "")
    assert '"Booking request": When a customer wants an appointment' in prompt
    assert "FORMS" not in compile_customer_support_prompt({"business_name": "Glow"}, "")


def test_send_form_tool_sends_a_published_form(meta, monkeypatch):
    db, _ = published_db(meta)
    db["tenants"].docs.append(dict(TENANT))
    sent = []

    async def fake_send(_db, _tenant, phone, doc, message=None):
        sent.append((phone, doc["name"]))
        return SendResult(ok=True)

    monkeypatch.setattr(tools, "get_database", lambda: db)
    monkeypatch.setattr(forms, "send_form_to", fake_send)
    config = {"configurable": {"tenant_id": "t1", "customer_phone": "923001111111"}}
    reply = run(tools.send_form.ainvoke({"form_name": "booking request"}, config=config))
    assert "was sent" in reply and sent == [("923001111111", "Booking request")]
    missing = run(tools.send_form.ainvoke({"form_name": "Survey"}, config=config))
    assert "no published form" in missing


def test_a_submitted_form_reaches_the_form_handler(monkeypatch):
    db = FakeDB()
    db["tenants"].docs.append({"tenant_id": "t1", "phone_number_id": "pn1"})
    app.dependency_overrides[get_database] = lambda: db
    got = []

    async def fake_handler(**kwargs):
        got.append(kwargs)

    monkeypatch.setattr(whatsapp_endpoint, "handle_form_reply", fake_handler)
    body = {"entry": [{"id": "waba1", "changes": [{"field": "messages", "value": {
        "metadata": {"phone_number_id": "pn1"},
        "messages": [{"id": "wamid.f1", "from": "923001111111", "type": "interactive",
                      "interactive": {"type": "nfm_reply", "nfm_reply": {"response_json": "{\"flow_token\": \"x\"}", "name": "flow"}}}],
    }}]}]}
    try:
        TestClient(app).post("/api/v1/whatsapp", json=body)
    finally:
        app.dependency_overrides.clear()
    assert got[0]["response_json"] == "{\"flow_token\": \"x\"}"
    assert got[0]["wamid"] == "wamid.f1"
