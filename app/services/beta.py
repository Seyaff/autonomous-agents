"""Features that are in beta for some owners only."""

from typing import Any, Dict

from core.settings import settings


def can_add_restaurant(user: Dict[str, Any]) -> bool:
    """A second (or later) restaurant is in beta: on for listed owners, or switched on per account."""
    if user.get("beta_multi_restaurant"):
        return True
    listed = {e.strip().lower() for e in (settings.BETA_OWNER_EMAILS or "").split(",") if e.strip()}
    return (user.get("email") or "").lower() in listed
