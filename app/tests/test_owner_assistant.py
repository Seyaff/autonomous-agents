"""The owner assistant saves through the same checks as the settings screens, and logs every change.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

import asyncio
from types import SimpleNamespace

from services.owner_assistant import _make_tools
from services.tenant_settings import TenantUpdatePayload, apply_tenant_update

TENANT_ID = "res_test_1"
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    async def find_one(self, query, projection=None):
        for d in self.docs:
            if all(d.get(k) == v for k, v in query.items()):
                return dict(d)
        return None

    async def update_one(self, query, update):
        doc = await self.find_one(query)
        if doc is None:
            return
        for key, value in update.get("$set", {}).items():
            target = next(d for d in self.docs if d["tenant_id"] == query["tenant_id"])
            cur = target
            parts = key.split(".")
            for part in parts[:-1]:
                cur = cur.setdefault(part, {})
            cur[parts[-1]] = value

    async def insert_one(self, doc):
        self.docs.append(dict(doc))

    async def update_many(self, query, update):
        return SimpleNamespace(matched_count=0)


class FakeDB(dict):
    def __getattr__(self, name):
        return self[name]


def make_db():
    tenant = {
        "tenant_id": TENANT_ID,
        "business_name": "Test Kitchen",
        "delivery_settings": {"flat_delivery_fee": 100},
        "agent_enabled": True,
        "timezone": "Asia/Karachi",
    }
    return FakeDB(tenants=FakeCollection([tenant]), settings_changes=FakeCollection([]), menu_items=FakeCollection([]))


def hours(closed_fridays=False):
    return [{"day": d, "open": "12:00", "close": "23:00", "closed": closed_fridays and d == "fri"} for d in DAYS]


def test_fee_change_is_saved_and_logged():
    db = make_db()
    payload = TenantUpdatePayload(flat_delivery_fee=150)
    changes = asyncio.run(apply_tenant_update(db, TENANT_ID, payload, user_id="u1", source="assistant"))
    assert changes == [{"field": "delivery_settings.flat_delivery_fee", "before": 100, "after": 150}]
    saved = db.tenants.docs[0]
    assert saved["delivery_settings"]["flat_delivery_fee"] == 150
    log = db.settings_changes.docs[0]
    assert log["source"] == "assistant" and log["user_id"] == "u1" and log["before"] == 100


def test_hours_must_cover_all_seven_days():
    db = make_db()
    payload = TenantUpdatePayload(operating_hours=[{"day": "mon"}])
    try:
        asyncio.run(apply_tenant_update(db, TENANT_ID, payload))
        raised = None
    except ValueError as e:
        raised = e
    assert raised is not None
    assert db.tenants.docs[0].get("operating_hours") is None


def test_unchanged_values_are_not_logged():
    db = make_db()
    assert asyncio.run(apply_tenant_update(db, TENANT_ID, TenantUpdatePayload(flat_delivery_fee=100))) == []
    assert db.settings_changes.docs == []


def test_unknown_setting_is_refused_with_a_message():
    db = make_db()
    tools = _make_tools(db, TENANT_ID, "u1", [])
    update = next(t for t in tools if t.name == "update_restaurant_settings")
    reply = asyncio.run(update.ainvoke({"changes": {"delivery_fee_typo": 99}}))
    assert reply.startswith("Not saved. Unknown setting")
    assert db.tenants.docs[0]["delivery_settings"]["flat_delivery_fee"] == 100


def test_pausing_the_agent_needs_confirmation():
    db = make_db()
    applied = []
    tools = _make_tools(db, TENANT_ID, "u1", applied)
    toggle = next(t for t in tools if t.name == "set_agent_enabled")
    reply = asyncio.run(toggle.ainvoke({"enabled": False}))
    assert "Not changed" in reply
    assert db.tenants.docs[0]["agent_enabled"] is True
    assert applied == []

    reply = asyncio.run(toggle.ainvoke({"enabled": False, "confirmed": True}))
    assert "paused" in reply
    assert db.tenants.docs[0]["agent_enabled"] is False
    assert applied == [{"field": "agent_enabled", "before": True, "after": False}]


def test_reply_settings_merge_with_what_is_already_saved():
    db = make_db()
    db.tenants.docs[0]["agent_settings"] = {"language": "match", "tone": "warm", "greeting": None,
                                            "escalate_on": {"refund": True, "complaint": True, "human_requested": True, "large_order_over": None}}
    applied = []
    tools = _make_tools(db, TENANT_ID, "u1", applied)
    reply_tool = next(t for t in tools if t.name == "update_reply_settings")
    reply = asyncio.run(reply_tool.ainvoke({"changes": {"language": "roman_urdu", "escalate_on": {"large_order_over": 5000}}}))
    assert reply == "Saved."
    saved = db.tenants.docs[0]["agent_settings"]
    assert saved["language"] == "roman_urdu" and saved["tone"] == "warm"
    assert saved["escalate_on"]["refund"] is True and saved["escalate_on"]["large_order_over"] == 5000
