"""Sold-out dishes: the day they apply to, name matching, and what the agent is told.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

from datetime import datetime, timezone

from agents.customer_support.prompt import compile_customer_support_prompt
from services.availability import is_sold_out, normalize, today_for


def test_today_follows_the_restaurant_timezone():
    # 20:30 UTC on 3 Oct is already 4 Oct in Karachi (UTC+5).
    late_utc = datetime(2026, 10, 3, 20, 30, tzinfo=timezone.utc)
    assert today_for({"timezone": "Asia/Karachi"}, late_utc) == "2026-10-04"
    assert today_for({"timezone": "UTC"}, late_utc) == "2026-10-03"


def test_unknown_timezone_falls_back_to_utc():
    now = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
    assert today_for({"timezone": "Not/AZone"}, now) == "2026-10-03"


def test_name_matching_ignores_case_and_extra_spaces():
    assert normalize("  Chicken   Karahi ") == "chicken karahi"
    assert is_sold_out("chicken karahi", ["Chicken Karahi"])
    assert not is_sold_out("Chicken Karahi Half", ["Chicken Karahi"])


def test_prompt_tells_the_agent_what_is_out_today():
    prompt = compile_customer_support_prompt({"business_name": "Diner", "sold_out": ["Chicken Karahi"]}, "")
    assert "NOT AVAILABLE RIGHT NOW" in prompt
    assert "Chicken Karahi" in prompt


def test_prompt_has_no_sold_out_block_when_everything_is_available():
    prompt = compile_customer_support_prompt({"business_name": "Diner"}, "")
    assert "NOT AVAILABLE RIGHT NOW" not in prompt
