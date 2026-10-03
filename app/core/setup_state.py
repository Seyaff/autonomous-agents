"""
Setup progress, country defaults and opening hours.

These are pure functions with no database access, so the rules can be tested
directly. The endpoints in api/v1/endpoints/tenant.py apply them.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator

SETUP_STEPS: List[str] = ["restaurant", "menu", "hours", "agent", "test", "whatsapp"]
SKIPPABLE = {"menu"}  # WhatsApp is required: without it the agent can't reply to customers
DAYS: List[str] = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# Currency and timezone are derived from the country on the server. The client never sends them.
COUNTRY_DEFAULTS: Dict[str, Tuple[str, str]] = {
    "PK": ("PKR", "Asia/Karachi"),
    "AE": ("AED", "Asia/Dubai"),
    "SA": ("SAR", "Asia/Riyadh"),
    "GB": ("GBP", "Europe/London"),
    "US": ("USD", "America/New_York"),
}


class SetupState(BaseModel):
    completed_steps: List[str] = Field(default_factory=list)
    skipped_steps: List[str] = Field(default_factory=list)
    completed_at: Optional[datetime] = None


class DayHours(BaseModel):
    day: str                       # "mon".."sun"
    open: str = "12:00"            # "HH:MM", 24-hour
    close: str = "23:30"
    closed: bool = False

    @field_validator("day")
    @classmethod
    def _day(cls, v: str) -> str:
        return normalize_day(v)

    @field_validator("open", "close")
    @classmethod
    def _time(cls, v: str) -> str:
        try:
            hours, minutes = v.split(":")
            if not (0 <= int(hours) <= 23 and 0 <= int(minutes) <= 59 and len(v) == 5):
                raise ValueError
        except ValueError:
            raise ValueError(f"time must be HH:MM, got {v!r}")
        return v


class EscalateRules(BaseModel):
    refund: bool = True
    complaint: bool = True
    human_requested: bool = True
    large_order_over: Optional[float] = None


class AgentSettings(BaseModel):
    language: Literal["match", "en", "roman_urdu"] = "match"
    tone: Literal["warm", "professional", "short"] = "warm"
    greeting: Optional[str] = None
    escalate_on: EscalateRules = Field(default_factory=EscalateRules)


def normalize_day(value: str) -> str:
    """Accepts 'mon', 'Monday', 'MON'. Returns 'mon'. Raises ValueError otherwise."""
    key = (value or "").strip().lower()[:3]
    if key not in DAYS:
        raise ValueError(f"unknown day: {value}")
    return key


def legacy_setup(tenant: Dict[str, Any]) -> SetupState:
    """Tenants created before setup existed were already onboarded, so they count as complete."""
    done_at = tenant.get("updated_at") or tenant.get("created_at") or datetime.now(timezone.utc)
    return SetupState(completed_steps=list(SETUP_STEPS), skipped_steps=[], completed_at=done_at)


def setup_of(tenant: Dict[str, Any]) -> SetupState:
    raw = tenant.get("setup")
    if raw is None:
        return legacy_setup(tenant)
    return SetupState(**raw)


def current_step(state: SetupState) -> str:
    """First step that is neither completed nor skipped, or 'done'."""
    handled = set(state.completed_steps) | set(state.skipped_steps)
    for step in SETUP_STEPS:
        if step not in handled:
            return step
    return "done"


def validate_action(state: SetupState, step: str, action: str) -> Optional[Tuple[int, str]]:
    """Returns (status_code, detail) if the action is not allowed, otherwise None."""
    if step not in SETUP_STEPS:
        return 400, f"Unknown setup step: {step}"
    if action not in ("complete", "skip"):
        return 400, "action must be 'complete' or 'skip'"
    if action == "skip" and step not in SKIPPABLE:
        return 400, f"The {step} step can't be skipped"

    index = SETUP_STEPS.index(step)
    done = set(state.completed_steps)
    for earlier in SETUP_STEPS[:index]:
        if earlier not in SKIPPABLE and earlier not in done:
            return 409, f"Finish the {earlier} step first"
    return None


def apply_action(state: SetupState, step: str, action: str) -> SetupState:
    completed = [s for s in state.completed_steps if s != step]
    skipped = [s for s in state.skipped_steps if s != step]
    if action == "complete":
        completed.append(step)
    else:
        skipped.append(step)
    return SetupState(completed_steps=completed, skipped_steps=skipped, completed_at=state.completed_at)


def derive_locale(country: str) -> Tuple[str, str]:
    """(currency, timezone) for a country code. Raises ValueError for unsupported countries."""
    code = (country or "").upper()
    if code not in COUNTRY_DEFAULTS:
        raise ValueError(f"unsupported country: {country}")
    return COUNTRY_DEFAULTS[code]


def _minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def normalize_hours(hours: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reads hours in the current shape and the older one (Monday, open_time,
    close_time, is_closed). Entries that can't be read are skipped, never raised,
    so a bad hours record can't stop the agent from replying."""
    out: List[Dict[str, Any]] = []
    for h in hours or []:
        try:
            entry = {
                "day": normalize_day(h.get("day", "")),
                "open": h.get("open") or h.get("open_time") or "12:00",
                "close": h.get("close") or h.get("close_time") or "23:30",
                "closed": bool(h.get("closed", h.get("is_closed", False))),
            }
            _minutes(entry["open"])
            _minutes(entry["close"])
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
        out.append(entry)
    return out


def hours_status(hours: List[Dict[str, Any]], tz_name: str, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Is the restaurant open right now?

    A closing time earlier than the opening time means the day closes after
    midnight, so that session counts toward the same day's entry.
    """
    hours = normalize_hours(hours)
    if not hours:
        return {"open_now": True, "reason": "no hours set"}

    by_day = {h["day"]: h for h in hours}
    local = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(tz_name))
    minute = local.hour * 60 + local.minute
    today = DAYS[local.weekday()]
    yesterday = DAYS[(local.weekday() - 1) % 7]

    def session(entry: Optional[Dict[str, Any]]) -> Optional[Tuple[int, int]]:
        if not entry or entry.get("closed"):
            return None
        return _minutes(entry["open"]), _minutes(entry["close"])

    today_session = session(by_day.get(today))
    if today_session:
        start, end = today_session
        if start <= end and start <= minute < end:
            return {"open_now": True, "closes_at": by_day[today]["close"]}
        if start > end and minute >= start:
            return {"open_now": True, "closes_at": by_day[today]["close"]}

    yesterday_session = session(by_day.get(yesterday))
    if yesterday_session:
        start, end = yesterday_session
        if start > end and minute < end:
            return {"open_now": True, "closes_at": by_day[yesterday]["close"]}

    return {"open_now": False, "opens_next": next_opening(by_day, local)}


def next_opening(by_day: Dict[str, Dict[str, Any]], local: datetime) -> Optional[str]:
    """Human-readable next opening, e.g. 'Mon 12:00'. None if the week has no open days."""
    for offset in range(0, 8):
        idx = (local.weekday() + offset) % 7
        day = DAYS[idx]
        entry = by_day.get(day)
        if not entry or entry.get("closed"):
            continue
        if offset == 0 and _minutes(entry["open"]) <= local.hour * 60 + local.minute:
            continue
        return f"{day.capitalize()} {entry['open']}"
    return None
