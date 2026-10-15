"""Any kind of business: the owner's description drives the agent, and orders can be delivery,
pickup, at the business's place, or a booking at a set time.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

import agents.customer_support.tools as tools
from agents.customer_support.prompt import NO_DESCRIPTION, compile_customer_support_prompt
from services.order_confirmation import confirmed_text, summary_text
from services.order_service import compute_totals, is_valid_transition, parse_booking_time, status_notice


def week(open_="09:00", close="21:00"):
    return [{"day": d, "open": open_, "close": close, "closed": False} for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]]


def salon(**overrides):
    base = {
        "tenant_id": "biz_salon",
        "business_name": "Glow Studio",
        "business_description": "A women's salon in DHA Lahore. Haircuts, colour and facials. Appointments only.",
        "currency": "PKR",
        "timezone": "Asia/Karachi",
        "operating_hours": week(),
        "order_types": ["booking"],
        "delivery_settings": {"flat_delivery_fee": 200, "avg_prep_time_minutes": 30},
        "agent_settings": {},
    }
    base.update(overrides)
    return base


# ------------------------------------------------------------------- prompt

def test_prompt_is_built_from_the_owners_description():
    prompt = compile_customer_support_prompt(salon(), "")
    assert "Glow Studio" in prompt
    assert "Haircuts, colour and facials. Appointments only." in prompt
    assert "Restaurant" not in prompt and "restaurant" not in prompt


def test_prompt_without_a_description_says_to_work_it_out():
    prompt = compile_customer_support_prompt(salon(business_description=""), "")
    assert NO_DESCRIPTION in prompt


def test_prompt_for_a_booking_business_asks_for_a_time_not_an_address():
    prompt = compile_customer_support_prompt(salon(), "")
    assert "the date and time (for a booking)" in prompt
    assert "the delivery address" not in prompt
    assert "Delivery areas" not in prompt
    assert "Delivery fee" not in prompt


def test_prompt_for_a_delivery_business_keeps_delivery_rules():
    prompt = compile_customer_support_prompt(salon(order_types=["delivery", "takeaway"], delivery_areas=["DHA"]), "")
    assert "the delivery address (for delivery)" in prompt
    assert "Delivery areas: DHA" in prompt
    assert "Order types: delivery, pickup" in prompt


# ------------------------------------------------------------------- totals

def test_delivery_fee_only_applies_to_delivery():
    items = [{"price": 1000, "quantity": 2}]
    tenant = salon()
    assert compute_totals(items, tenant, "delivery")[:3] == (2000.0, 200.0, 2200.0)
    assert compute_totals(items, tenant, "booking")[:3] == (2000.0, 0.0, 2000.0)
    assert compute_totals(items, tenant, "takeaway")[:3] == (2000.0, 0.0, 2000.0)


def test_catalog_prices_beat_the_models_prices():
    catalog = {"haircut": {"name": "Haircut", "price": 1500}}
    priced = tools.price_items(
        [{"name": "haircut ", "quantity": 1, "price": 99}, {"name": "Custom thing", "quantity": 2, "price": 300}],
        catalog,
    )
    assert priced[0]["name"] == "Haircut" and priced[0]["price"] == 1500.0
    assert priced[1]["price"] == 300.0


def test_an_order_without_delivery_can_finish_without_going_out_for_delivery():
    assert is_valid_transition("preparing", "delivered")
    assert is_valid_transition("preparing", "out_for_delivery")


# ----------------------------------------------------------------- bookings

def test_booking_time_is_read_in_the_business_timezone():
    at = parse_booking_time("2026-10-20 16:30", "Asia/Karachi")
    assert at.tzinfo == ZoneInfo("Asia/Karachi")
    assert at.astimezone(timezone.utc).hour == 11


def test_bad_booking_time_says_what_format_to_use():
    with pytest.raises(ValueError, match="YYYY-MM-DD HH:MM"):
        parse_booking_time("tomorrow at 4", "Asia/Karachi")


def test_booking_summary_and_confirmation_show_the_time():
    order = {"order_id": "ORD-1", "order_type": "booking", "scheduled_for_local": "2026-10-20 16:30",
             "customer_name": "Sana", "items": [{"name": "Facial", "quantity": 1}], "payment_method": "cash",
             "currency": "PKR", "total_amount": 3000.0, "delivery_fee": 0.0}
    text = summary_text(order)
    assert "Please check your booking, Sana" in text
    assert "Booked for: 2026-10-20 16:30" in text
    assert "Delivery to" not in text and "incl. delivery" not in text
    assert "2026-10-20 16:30" in confirmed_text(order)


def test_pickup_summary_has_no_address():
    order = {"order_id": "ORD-2", "order_type": "takeaway", "customer_name": "Ali", "items": [],
             "currency": "PKR", "total_amount": 500.0, "delivery_fee": 0.0}
    assert "Pickup" in summary_text(order)
    assert "Delivery to" not in summary_text(order)


def test_status_notices_fit_the_order_type():
    assert "booking ORD-1 is confirmed" in status_notice({"order_id": "ORD-1", "order_type": "booking"}, "accepted")
    assert status_notice({"order_id": "ORD-1", "order_type": "booking"}, "preparing") is None
    assert "on the way" in status_notice({"order_id": "ORD-2", "order_type": "delivery"}, "out_for_delivery")
    assert "ready" in status_notice({"order_id": "ORD-3", "order_type": "takeaway"}, "out_for_delivery")
    # Orders saved before order types existed are delivery orders.
    assert "delivered" in status_notice({"order_id": "ORD-4"}, "delivered")


# ------------------------------------------------------ the order tool itself

class FakeOrders:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(doc)

        class Result:
            inserted_id = "x"
        return Result()

    async def update_one(self, *_args, **_kwargs):
        return None


class FakeTenants:
    def __init__(self, tenant):
        self.tenant = tenant

    async def find_one(self, *_args, **_kwargs):
        return dict(self.tenant)


@pytest.fixture
def order_db(monkeypatch):
    def make(tenant):
        db = {"tenants": FakeTenants(tenant), "orders": FakeOrders()}
        monkeypatch.setattr(tools, "get_database", lambda: db)

        async def no_catalog(*_a, **_k):
            return {"facial": {"name": "Facial", "price": 3000}}

        async def nothing_sold_out(*_a, **_k):
            return []

        async def nothing_waiting(*_a, **_k):
            return None

        sent = []

        async def fake_send(_db, _tenant, order):
            sent.append(order)

            class Result:
                ok = True
                error_message = None
            return Result()

        monkeypatch.setattr(tools, "catalog_prices", no_catalog)
        monkeypatch.setattr(tools, "sold_out_names", nothing_sold_out)
        monkeypatch.setattr(tools, "find_awaiting", nothing_waiting)
        monkeypatch.setattr(tools, "send_summary", fake_send)
        return db, sent
    return make


def place(args):
    config = {"configurable": {"tenant_id": "biz_salon", "customer_phone": "923001234567"}}
    return asyncio.run(tools.create_order_tool.ainvoke(args, config=config))


def future_slot(days=2, hour=15):
    local = datetime.now(ZoneInfo("Asia/Karachi")) + timedelta(days=days)
    return local.replace(hour=hour, minute=0).strftime("%Y-%m-%d %H:%M")


def test_a_booking_is_saved_with_its_time_and_no_delivery_fee(order_db):
    db, sent = order_db(salon())
    reply = place({"items": [{"name": "Facial", "quantity": 1, "price": 1}], "order_type": "booking",
                   "scheduled_for": future_slot(), "customer_name": "Sana"})
    assert "Summary sent" in reply
    order = db["orders"].docs[0]
    assert order["order_type"] == "booking"
    assert order["scheduled_for_local"] == future_slot()
    assert order["delivery_address"] is None
    assert order["delivery_fee"] == 0.0 and order["total_amount"] == 3000.0
    assert sent and sent[0]["order_id"] == order["order_id"]


def test_a_booking_outside_opening_hours_is_refused(order_db):
    db, _ = order_db(salon())
    reply = place({"items": [{"name": "Facial", "quantity": 1, "price": 1}], "order_type": "booking",
                   "scheduled_for": future_slot(hour=23), "customer_name": "Sana"})
    assert "closed at" in reply
    assert db["orders"].docs == []


def test_a_booking_in_the_past_is_refused(order_db):
    db, _ = order_db(salon())
    reply = place({"items": [{"name": "Facial", "quantity": 1, "price": 1}], "order_type": "booking",
                   "scheduled_for": future_slot(days=-2), "customer_name": "Sana"})
    assert "already passed" in reply
    assert db["orders"].docs == []


def test_an_order_type_the_business_doesnt_offer_is_refused(order_db):
    db, _ = order_db(salon())
    reply = place({"items": [{"name": "Facial", "quantity": 1, "price": 1}], "order_type": "delivery",
                   "delivery_address": "House 1", "customer_name": "Sana"})
    assert "doesn't take delivery orders" in reply
    assert db["orders"].docs == []


def test_delivery_needs_an_address(order_db):
    db, _ = order_db(salon(order_types=["delivery"], operating_hours=[]))
    reply = place({"items": [{"name": "Facial", "quantity": 1, "price": 1}], "order_type": "delivery",
                   "customer_name": "Sana"})
    assert "delivery address" in reply
    assert db["orders"].docs == []
