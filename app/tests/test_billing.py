"""Billing part 1: plans, trial, and the agent gate. Values come from PRICING.md.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

import asyncio
from datetime import datetime, timedelta, timezone

from services.billing import (
    PLANS,
    TRIAL_CHAT_CAP,
    agent_allowed,
    allowance_for,
    current_period,
    new_subscription,
    plan_for,
    subscription_for,
)

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    async def find_one(self, query, *_, **__):
        for d in self.docs:
            if all(d.get(k) == v for k, v in query.items()):
                return d
        return None


class FakeDb(dict):
    pass


def db_with_usage(used: int, tenant_id="t1"):
    db = FakeDb()
    db["usage_counters"] = FakeCollection([{"tenant_id": tenant_id, "period": current_period(NOW), "ai_conversations": used}])
    return db


def tenant_with(sub, tenant_id="t1"):
    return {"tenant_id": tenant_id, "subscription": sub}


def test_plans_match_pricing_md():
    assert PLANS["basic"]["price_monthly_pkr"] == 2999 and PLANS["basic"]["ai_conversations_per_month"] == 200
    assert PLANS["standard"]["price_monthly_pkr"] == 5999 and PLANS["standard"]["ai_conversations_per_month"] == 600
    assert PLANS["pro"]["price_monthly_pkr"] == 11999 and PLANS["pro"]["ai_conversations_per_month"] == 1500
    assert PLANS["basic"]["price_yearly_pkr"] == 29990
    assert PLANS["standard"]["price_yearly_pkr"] == 59990
    assert PLANS["pro"]["price_yearly_pkr"] == 119990


def test_new_restaurant_gets_a_14_day_trial():
    sub = new_subscription(NOW)
    assert sub["status"] == "trialing"
    assert sub["trial_ends_at"] == NOW + timedelta(days=3)
    assert sub["plan"] == "basic"


def test_trial_allows_agent_before_end_and_cap():
    ok, _ = asyncio.run(agent_allowed(db_with_usage(10), tenant_with(new_subscription(NOW)), now=NOW))
    assert ok


def test_trial_stops_agent_when_it_ends():
    sub = {**new_subscription(NOW), "trial_ends_at": NOW - timedelta(minutes=1)}
    ok, reason = asyncio.run(agent_allowed(db_with_usage(10), tenant_with(sub), now=NOW))
    assert not ok and reason == "trial ended"


def test_trial_stops_agent_at_100_chats():
    ok, reason = asyncio.run(agent_allowed(db_with_usage(TRIAL_CHAT_CAP), tenant_with(new_subscription(NOW)), now=NOW))
    assert not ok and reason == "trial chat cap reached"


def test_paused_and_canceled_stop_agent():
    for status in ("paused", "canceled"):
        ok, _ = asyncio.run(agent_allowed(db_with_usage(0), tenant_with({"status": status, "plan": "basic"}), now=NOW))
        assert not ok


def test_active_and_past_due_keep_agent_working():
    for status in ("active", "past_due"):
        ok, _ = asyncio.run(agent_allowed(db_with_usage(900), tenant_with({"status": status, "plan": "basic"}), now=NOW))
        assert ok


def test_trial_allowance_is_the_cap_not_the_plan():
    assert allowance_for(tenant_with(new_subscription(NOW))) == TRIAL_CHAT_CAP
    assert allowance_for(tenant_with({"status": "active", "plan": "standard"})) == 600


def test_legacy_tenants_map_to_new_plans():
    assert plan_for({"plan": "starter"})["key"] == "basic"
    assert plan_for({"plan": "growth"})["key"] == "standard"
    assert plan_for({"plan": "scale"})["key"] == "pro"
    assert plan_for({})["key"] == "standard"  # no plan was the old default (growth)
    assert subscription_for({"plan": "scale"})["plan"] == "pro"
