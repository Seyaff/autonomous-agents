"""The owner's agent: its tools read and change the business through the same services as the screens, and anything
that reaches customers or can't be undone waits for the owner's Confirm.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

import asyncio
from datetime import datetime, timedelta, timezone

from services import assistant_tools, owner_actions, owner_assistant
from services.assistant_tools import Turn, decide_action, make_tools
from tests.fake_mongo import FakeCollection, FakeDB

TENANT_ID = "biz_1"
NOW = datetime.now(timezone.utc)


def make_db():
    db = FakeDB()
    db["tenants"] = FakeCollection([{
        "tenant_id": TENANT_ID, "business_name": "Glow Salon", "currency": "PKR", "timezone": "Asia/Karachi",
        "agent_enabled": True, "business_description": "A hair and beauty salon taking bookings.",
    }])
    db["menu_items"] = FakeCollection([
        {"tenant_id": TENANT_ID, "name": "Haircut", "category": "Hair", "price": 1500.0},
        {"tenant_id": TENANT_ID, "name": "Hair Colour", "category": "Hair", "price": 6000.0},
        {"tenant_id": TENANT_ID, "name": "Facial", "category": "Skin", "price": 3000.0},
        {"tenant_id": "someone_else", "name": "Manicure", "price": 1.0},
    ])
    db["orders"] = FakeCollection([
        {"tenant_id": TENANT_ID, "order_id": "ORD-1", "status": "pending", "customer_name": "Ayesha", "customer_phone": "923001112222",
         "items": [{"name": "Haircut", "quantity": 1, "price": 1500}], "total_amount": 1500, "currency": "PKR",
         "order_type": "booking", "created_at": NOW - timedelta(minutes=30),
         "status_history": [{"status": "pending", "at": NOW - timedelta(minutes=30), "by": "agent"}]},
        {"tenant_id": TENANT_ID, "order_id": "ORD-2", "status": "delivered", "customer_name": "Bilal", "customer_phone": "923003334444",
         "items": [{"name": "Facial", "quantity": 2, "price": 3000}], "total_amount": 6000, "currency": "PKR",
         "order_type": "booking", "created_at": NOW - timedelta(minutes=10), "status_history": []},
        {"tenant_id": TENANT_ID, "order_id": "ORD-OLD", "status": "delivered", "customer_name": "Ayesha", "customer_phone": "923001112222",
         "items": [{"name": "Haircut", "quantity": 1, "price": 1500}], "total_amount": 1500, "currency": "PKR",
         "created_at": NOW - timedelta(days=40), "status_history": []},
        {"tenant_id": "someone_else", "order_id": "ORD-X", "status": "pending", "total_amount": 999999, "created_at": NOW},
    ])
    db["conversations"] = FakeCollection([
        {"tenant_id": TENANT_ID, "conversation_id": "conv_a", "customer_name": "Ayesha", "customer_phone": "923001112222",
         "status": "open", "handled_by": "agent", "escalation": {"active": True, "reason": "refund"},
         "last_message": {"content": "I want my money back"}, "last_activity_at": NOW},
        {"tenant_id": TENANT_ID, "conversation_id": "conv_b", "customer_name": "Bilal", "customer_phone": "923003334444",
         "status": "open", "handled_by": "agent", "last_message": {"content": "thanks"}, "last_activity_at": NOW - timedelta(hours=30)},
    ])
    db["messages"] = FakeCollection([
        {"tenant_id": TENANT_ID, "conversation_id": "conv_a", "sender": "customer", "sender_phone": "923001112222",
         "content": "I want my money back", "created_at": NOW - timedelta(hours=1)},
        {"tenant_id": TENANT_ID, "conversation_id": "conv_b", "sender": "customer", "sender_phone": "923003334444",
         "content": "thanks", "created_at": NOW - timedelta(hours=30)},
    ])
    return db


def tools_for(db, turn=None):
    turn = turn if turn is not None else Turn()
    return {t.name: t for t in make_tools(db, TENANT_ID, "u1", turn)}, turn


def call(tool, **args):
    return asyncio.run(tool.ainvoke(args))


def test_catalog_items_are_added_changed_and_matched_by_name():
    db = make_db()
    tools, turn = tools_for(db)

    assert call(tools["add_catalog_item"], name="Beard Trim", price=800, category="Hair") == "Added Beard Trim."
    assert "already in the catalog" in call(tools["add_catalog_item"], name="haircut", price=1)

    assert call(tools["update_catalog_item"], name="facial", changes={"price": 3500}) == "Saved."
    facial = next(d for d in db.menu_items.docs if d["name"] == "Facial")
    assert facial["price"] == 3500

    # "hair" matches two items, so the agent has to ask which one.
    assert "More than one item matches" in call(tools["update_catalog_item"], name="hair", changes={"price": 1})
    assert "No item named" in call(tools["set_item_unavailable"], name="manicure", sold_out=True)
    assert [c["field"] for c in turn.applied] == ["menu.added", "menu.price"]
    assert len(db.settings_changes.docs) == 2


def test_deleting_an_item_waits_for_confirm():
    db = make_db()
    tools, turn = tools_for(db)

    reply = call(tools["remove_catalog_item"], name="Facial")
    assert "Confirm" in reply and len(turn.actions) == 1
    assert any(d["name"] == "Facial" for d in db.menu_items.docs)

    outcome = asyncio.run(decide_action(db, TENANT_ID, "u1", turn.actions[0]["action_id"], confirm=True))
    assert outcome["status"] == "done"
    assert not any(d["name"] == "Facial" for d in db.menu_items.docs)


def test_an_action_runs_once_and_can_be_cancelled_or_expire():
    db = make_db()
    tools, turn = tools_for(db)
    call(tools["remove_catalog_item"], name="Facial")
    call(tools["remove_catalog_item"], name="Haircut")
    first, second = (a["action_id"] for a in turn.actions)

    assert asyncio.run(decide_action(db, TENANT_ID, "u1", first, confirm=True))["status"] == "done"
    again = asyncio.run(decide_action(db, TENANT_ID, "u1", first, confirm=True))
    assert again["status"] == "done" and again["changes"] == []

    assert asyncio.run(decide_action(db, TENANT_ID, "u1", second, confirm=False))["status"] == "cancelled"
    assert any(d["name"] == "Haircut" for d in db.menu_items.docs)

    call(tools["remove_catalog_item"], name="Hair Colour")
    stale = turn.actions[-1]["action_id"]
    db.assistant_actions.docs[-1]["created_at"] = NOW - timedelta(hours=2)
    assert asyncio.run(decide_action(db, TENANT_ID, "u1", stale, confirm=True))["status"] == "expired"
    assert any(d["name"] == "Hair Colour" for d in db.menu_items.docs)

    # Another business can't run this business's actions.
    call(tools["remove_catalog_item"], name="Hair Colour")
    assert asyncio.run(decide_action(db, "someone_else", "u9", turn.actions[-1]["action_id"], True))["status"] == "missing"


def test_orders_and_numbers_come_from_this_business_only():
    db = make_db()
    tools, _ = tools_for(db)

    today = call(tools["find_orders"], days=1)
    assert "2 order(s)" in today and "ORD-1" in today and "ORD-OLD" not in today and "ORD-X" not in today
    assert "ORD-1" in call(tools["find_orders"], status="open") and "ORD-2" not in call(tools["find_orders"], status="open")
    assert "Unknown status" in call(tools["find_orders"], status="lost")

    summary = call(tools["sales_summary"], days=1)
    assert "Orders: 2" in summary
    assert "PKR 6,000" in summary  # the pending order isn't revenue yet
    assert "Facial x2" in summary

    regulars = call(tools["find_customers"], min_orders=2)
    assert "Ayesha" in regulars and "Bilal" not in regulars


def test_order_moves_on_directly_but_cancelling_needs_confirm(monkeypatch):
    async def told(*_a, **_k):
        return True

    async def quiet(**_k):
        return None

    monkeypatch.setattr(owner_actions, "notify_customer_status", told)
    monkeypatch.setattr(owner_actions, "broadcast_order_update", quiet)
    db = make_db()
    tools, turn = tools_for(db)

    assert "now accepted" in call(tools["update_order_status"], order_id="ORD-1", status="accepted")
    order = next(o for o in db.orders.docs if o["order_id"] == "ORD-1")
    assert order["status"] == "accepted" and order["status_history"][-1]["by"] == "owner"
    assert turn.applied[-1] == {"field": "order.ORD-1", "before": "pending", "after": "accepted"}

    assert "Not changed" in call(tools["update_order_status"], order_id="ORD-1", status="delivered")
    assert "can't be cancelled" in call(tools["update_order_status"], order_id="ORD-2", status="cancelled")

    call(tools["update_order_status"], order_id="ORD-1", status="cancelled", note="customer asked")
    assert order["status"] == "accepted" and next(o for o in db.orders.docs if o["order_id"] == "ORD-1")["status"] == "accepted"
    outcome = asyncio.run(decide_action(db, TENANT_ID, "u1", turn.actions[-1]["action_id"], True))
    assert outcome["status"] == "done"
    assert next(o for o in db.orders.docs if o["order_id"] == "ORD-1")["status"] == "cancelled"


def test_chats_are_found_read_and_messaged_only_after_confirm(monkeypatch):
    sent = []

    async def fake_reply(db, tenant, conversation, text, user_id, message_type="text"):
        sent.append((conversation["conversation_id"], text))
        return True, None

    monkeypatch.setattr(owner_actions, "owner_reply", fake_reply)
    db = make_db()
    tools, turn = tools_for(db)

    needs_you = call(tools["find_conversations"], group="needs_you")
    assert "conv_a" in needs_you and "conv_b" not in needs_you
    assert "I want my money back" in call(tools["read_conversation"], conversation_id="conv_a")

    # Bilal wrote 30 hours ago, so only a template can reach him.
    assert "Can't send" in call(tools["message_customer"], conversation_id="conv_b", text="Hi!")

    call(tools["message_customer"], conversation_id="conv_a", text="Refund is on its way.")
    assert sent == [] and turn.actions[-1]["detail"] == "Refund is on its way."
    asyncio.run(decide_action(db, TENANT_ID, "u1", turn.actions[-1]["action_id"], True))
    assert sent == [("conv_a", "Refund is on its way.")]


def test_open_page_only_knows_dashboard_pages():
    db = make_db()
    tools, turn = tools_for(db)
    call(tools["open_page"], page="inbox", conversation_id="conv_a")
    call(tools["open_page"], page="Orders")
    assert "Unknown page" in call(tools["open_page"], page="https://evil.example")
    assert turn.pages == ["/dashboard/inbox/conv_a", "/dashboard/orders"]


def test_prompt_knows_the_business_and_the_time():
    tenant = make_db().tenants.docs[0]
    prompt = owner_assistant.system_prompt(tenant, now=datetime(2026, 10, 15, 7, 0, tzinfo=timezone.utc))
    assert "Glow Salon" in prompt and "PKR" in prompt and "hair and beauty salon" in prompt
    assert "Thursday 15 October 2026, 12:00 PM" in prompt  # Karachi is UTC+5


class _Chunk:
    def __init__(self, content):
        self.content = content


def test_stream_sends_confirm_cards_and_pages_and_saves_them(monkeypatch):
    db = make_db()

    class Scripted:
        def __init__(self, tools):
            self.tools = {t.name: t for t in tools}

        async def astream_events(self, state, version):
            yield {"event": "on_tool_start", "name": "remove_catalog_item", "run_id": "r1", "data": {}}
            await self.tools["remove_catalog_item"].ainvoke({"name": "Facial"})
            yield {"event": "on_tool_end", "name": "remove_catalog_item", "run_id": "r1", "data": {}}
            await self.tools["open_page"].ainvoke({"page": "catalog"})
            yield {"event": "on_chat_model_stream", "data": {"chunk": _Chunk("Press Delete to remove Facial.")}}

    monkeypatch.setattr(owner_assistant, "_agent", lambda provider, tools: Scripted(tools))

    async def run():
        return [e async for e in owner_assistant.stream_owner_turn(db, TENANT_ID, "u1", "remove facial")]

    events = asyncio.run(run())
    kinds = [e["type"] for e in events]
    assert kinds[:3] == ["tool", "tool_end", "confirm"] and "navigate" in kinds and kinds[-1] == "done"
    action = next(e["action"] for e in events if e["type"] == "confirm")
    assert action["summary"] == "Delete Facial from the catalog" and "args" not in action

    history = asyncio.run(owner_assistant.load_transcript(db, TENANT_ID, "u1"))
    assert history[-1]["actions"][0]["status"] == "pending"

    asyncio.run(owner_assistant.decide(db, TENANT_ID, "u1", action["action_id"], True))
    history = asyncio.run(owner_assistant.load_transcript(db, TENANT_ID, "u1"))
    assert history[-2]["actions"][0]["status"] == "done"
    assert history[-1]["content"] == "Facial is removed from the catalog."


def test_every_tool_has_a_description():
    tools, _ = tools_for(make_db())
    assert len(tools) >= 25
    assert all(t.description and len(t.description) > 30 for t in tools.values())
    assert set(assistant_tools.EXECUTORS) >= {"pause_agent", "message_customer", "cancel_order", "delete_item", "send_campaign"}
