"""Pure-logic tests for setup, hours, locale and the support prompt.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from agents.customer_support.prompt import compile_customer_support_prompt
from core.setup_state import (
    AgentSettings,
    DayHours,
    SetupState,
    apply_action,
    current_step,
    derive_locale,
    hours_status,
    legacy_setup,
    normalize_day,
    setup_of,
    validate_action,
)


# ---------------------------------------------------------------- setup steps

def test_new_tenant_starts_at_menu_after_restaurant():
    state = SetupState(completed_steps=["restaurant"])
    assert current_step(state) == "menu"


def test_skipped_steps_count_as_handled():
    state = SetupState(completed_steps=["restaurant"], skipped_steps=["menu"])
    assert current_step(state) == "hours"


def test_done_when_everything_handled():
    state = SetupState(
        completed_steps=["restaurant", "hours", "agent", "test"],
        skipped_steps=["menu", "whatsapp"],
    )
    assert current_step(state) == "done"


def test_cannot_skip_a_required_step():
    problem = validate_action(SetupState(), "hours", "skip")
    assert problem and problem[0] == 400


def test_unknown_step_is_400():
    problem = validate_action(SetupState(), "payments", "complete")
    assert problem and problem[0] == 400


def test_unknown_action_is_400():
    problem = validate_action(SetupState(completed_steps=["restaurant"]), "menu", "delete")
    assert problem and problem[0] == 400


def test_later_step_blocked_until_required_earlier_step_done():
    # hours needs restaurant (done) and nothing else required before it except menu,
    # which is skippable, so hours is allowed straight away.
    assert validate_action(SetupState(completed_steps=["restaurant"]), "hours", "complete") is None
    # agent needs hours, which isn't done yet.
    problem = validate_action(SetupState(completed_steps=["restaurant"]), "agent", "complete")
    assert problem and problem[0] == 409


def test_skipping_optional_step_does_not_block_later_steps():
    state = apply_action(SetupState(completed_steps=["restaurant"]), "menu", "skip")
    assert validate_action(state, "hours", "complete") is None


def test_apply_moves_a_step_between_lists():
    state = apply_action(SetupState(completed_steps=["restaurant"], skipped_steps=["menu"]), "menu", "complete")
    assert "menu" in state.completed_steps
    assert "menu" not in state.skipped_steps


def test_legacy_tenant_without_setup_counts_as_complete():
    tenant = {"tenant_id": "res_old", "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    state = setup_of(tenant)
    assert current_step(state) == "done"
    assert state.completed_at is not None


def test_legacy_setup_is_all_steps():
    assert current_step(legacy_setup({})) == "done"


# -------------------------------------------------------------------- locale

@pytest.mark.parametrize("country,currency,tz", [
    ("PK", "PKR", "Asia/Karachi"),
    ("ae", "AED", "Asia/Dubai"),          # case-insensitive
    ("GB", "GBP", "Europe/London"),
    ("US", "USD", "America/New_York"),
])
def test_country_derives_currency_and_timezone(country, currency, tz):
    assert derive_locale(country) == (currency, tz)


def test_unsupported_country_raises():
    with pytest.raises(ValueError):
        derive_locale("FR")


# --------------------------------------------------------------------- hours

def week(open_="12:00", close="23:30", closed_days=()):
    return [
        {"day": d, "open": open_, "close": close, "closed": d in closed_days}
        for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    ]


def karachi_utc(day_index: int, hour: int, minute: int = 0) -> datetime:
    """A UTC datetime that reads as day_index (0 = Monday), hour:minute in Asia/Karachi."""
    local_minutes = hour * 60 + minute - 5 * 60
    days = day_index
    if local_minutes < 0:
        local_minutes += 24 * 60
        days -= 1
    return datetime(2026, 10, 5, tzinfo=timezone.utc).replace(
        day=5 + days, hour=local_minutes // 60, minute=local_minutes % 60
    )


def test_open_during_the_day():
    status = hours_status(week(), "Asia/Karachi", karachi_utc(0, 14))
    assert status["open_now"] is True
    assert status["closes_at"] == "23:30"


def test_closed_before_opening_reports_next_opening():
    status = hours_status(week(), "Asia/Karachi", karachi_utc(0, 9))
    assert status["open_now"] is False
    assert status["opens_next"] == "Mon 12:00"


def test_closed_day_is_skipped_for_next_opening():
    hours = week(closed_days=("tue",))
    status = hours_status(hours, "Asia/Karachi", karachi_utc(1, 9))
    assert status["open_now"] is False
    assert status["opens_next"] == "Wed 12:00"


def test_session_that_closes_after_midnight_counts_toward_same_day():
    # Friday opens 18:00 and closes 02:00 on Saturday.
    hours = week(open_="12:00", close="23:30")
    hours[4] = {"day": "fri", "open": "18:00", "close": "02:00", "closed": False}
    # Saturday 01:00 is still Friday's session.
    status = hours_status(hours, "Asia/Karachi", karachi_utc(5, 1))
    assert status["open_now"] is True
    assert status["closes_at"] == "02:00"


def test_after_midnight_session_closed_once_it_ends():
    hours = week()
    hours[4] = {"day": "fri", "open": "18:00", "close": "02:00", "closed": False}
    status = hours_status(hours, "Asia/Karachi", karachi_utc(5, 3))
    assert status["open_now"] is False


def test_no_hours_means_open():
    assert hours_status([], "Asia/Karachi")["open_now"] is True


def test_normalize_day_accepts_long_names():
    assert normalize_day("Monday") == "mon"
    assert normalize_day("SUN") == "sun"
    with pytest.raises(ValueError):
        normalize_day("Funday")


def test_day_hours_rejects_bad_time():
    with pytest.raises(ValidationError):
        DayHours(day="mon", open="25:00", close="23:00")
    with pytest.raises(ValidationError):
        DayHours(day="mon", open="9am", close="23:00")


def test_day_hours_normalizes_day_name():
    assert DayHours(day="Monday", open="09:00", close="22:00").day == "mon"


# ------------------------------------------------------------ agent settings

def test_agent_settings_rejects_unknown_language():
    with pytest.raises(ValidationError):
        AgentSettings(language="klingon")


def test_agent_settings_defaults():
    s = AgentSettings()
    assert (s.language, s.tone) == ("match", "warm")
    assert s.escalate_on.refund and s.escalate_on.complaint and s.escalate_on.human_requested
    assert s.escalate_on.large_order_over is None


# ------------------------------------------------------------------- prompt

def tenant(**overrides):
    base = {
        "tenant_id": "res_t",
        "business_name": "Test Diner",
        "currency": "PKR",
        "timezone": "Asia/Karachi",
        "operating_hours": week(),
        "agent_settings": {},
    }
    base.update(overrides)
    return base


def test_prompt_states_open_or_closed_from_hours():
    open_prompt = compile_customer_support_prompt(tenant(), "", now=karachi_utc(0, 14))
    closed_prompt = compile_customer_support_prompt(tenant(), "", now=karachi_utc(0, 9))
    assert "Right now: OPEN" in open_prompt
    assert "Right now: CLOSED" in closed_prompt


def test_prompt_escalation_lists_only_enabled_triggers():
    t = tenant(agent_settings={"escalate_on": {"refund": True, "complaint": False, "human_requested": False}})
    prompt = compile_customer_support_prompt(t, "")
    assert "a refund request" in prompt
    assert "a complaint" not in prompt
    assert "asks for a person" not in prompt


def test_prompt_with_no_escalation_says_so():
    t = tenant(agent_settings={"escalate_on": {"refund": False, "complaint": False, "human_requested": False}})
    prompt = compile_customer_support_prompt(t, "")
    assert "No automatic escalation is set" in prompt


def test_prompt_large_order_trigger_uses_currency():
    t = tenant(agent_settings={"escalate_on": {"large_order_over": 5000}})
    assert "an order over PKR 5000" in compile_customer_support_prompt(t, "")


def test_prompt_language_and_tone_follow_settings():
    t = tenant(agent_settings={"language": "en", "tone": "short"})
    prompt = compile_customer_support_prompt(t, "")
    assert "Always reply in English" in prompt
    assert "One line per reply" in prompt
    assert "Roman Urdu (Urdu written in English letters), even" not in prompt


def test_prompt_custom_greeting_is_used():
    t = tenant(agent_settings={"greeting": "Welcome to the Diner!"})
    assert "Welcome to the Diner!" in compile_customer_support_prompt(t, "")


def test_prompt_lists_delivery_rules_when_set():
    t = tenant(delivery_areas=["Gulberg", "DHA"], min_order_amount=800,
               payment_methods=["cash_on_delivery"], order_types=["delivery", "takeaway"])
    prompt = compile_customer_support_prompt(t, "")
    assert "Gulberg, DHA" in prompt
    assert "Minimum order: PKR 800" in prompt
    assert "cash on delivery" in prompt
    assert "Order types: delivery, takeaway" in prompt
