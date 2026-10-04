"""
Sign-in sessions. One session per sign-in on one device.

A session holds a hash of its current refresh token, plus the hashes of the refresh tokens
it has already rotated away from. Each refresh replaces the current token, so a stolen
refresh token works once at most. If an old one comes back, someone else has it: the whole
session is revoked and the owner has to sign in again.

Only hashes are stored. The plain refresh token exists only in the owner's browser cookie.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

SESSIONS = "sessions"
IDLE_TIMEOUT = timedelta(days=30)  # signed out after 30 days without a refresh
ABSOLUTE_LIFETIME = timedelta(days=90)  # and no session lasts longer than 90 days
PREVIOUS_HASHES_KEPT = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


async def ensure_session_indexes(db) -> None:
    await db[SESSIONS].create_index([("refresh_hash", 1)], name="sessions_refresh_hash")
    await db[SESSIONS].create_index([("user_id", 1), ("revoked_at", 1)], name="sessions_user_active")


async def create_session(db, user_id: str, user_agent: str = "") -> Tuple[Dict[str, Any], str]:
    """Starts a session for a sign-in. Returns (session, refresh token to set in the cookie)."""
    now = _now()
    refresh = new_refresh_token()
    session = {
        "session_id": f"ses_{secrets.token_hex(12)}",
        "user_id": user_id,
        "refresh_hash": hash_token(refresh),
        "previous_hashes": [],
        "user_agent": (user_agent or "")[:300],
        "created_at": now,
        "last_used_at": now,
        "idle_expires_at": now + IDLE_TIMEOUT,
        "absolute_expires_at": now + ABSOLUTE_LIFETIME,
        "revoked_at": None,
        "revoked_reason": None,
    }
    await db[SESSIONS].insert_one(session)
    return session, refresh


async def rotate(db, refresh_token: str) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """Trades a refresh token for a new one.

    Returns (session, new refresh token, None) on success, or (None, None, reason) when the
    token can't be used. The reason is 'invalid', 'expired', 'revoked' or 'reused'.
    """
    presented = hash_token(refresh_token)
    now = _now()

    session = await db[SESSIONS].find_one({"refresh_hash": presented})
    if session is None:
        # Not the current token. Has it been used before? Then it's been copied.
        session = await db[SESSIONS].find_one({"previous_hashes": presented})
        if session is not None and session.get("revoked_at") is None:
            await revoke_session(db, session["session_id"], reason="reused")
            return None, None, "reused"
        return None, None, "invalid"

    if session.get("revoked_at") is not None:
        return None, None, "revoked"
    if now >= _utc(session["idle_expires_at"]) or now >= _utc(session["absolute_expires_at"]):
        await revoke_session(db, session["session_id"], reason="expired")
        return None, None, "expired"

    new_refresh = new_refresh_token()
    previous = [session["refresh_hash"], *session.get("previous_hashes", [])][:PREVIOUS_HASHES_KEPT]
    await db[SESSIONS].update_one(
        {"session_id": session["session_id"]},
        {"$set": {
            "refresh_hash": hash_token(new_refresh),
            "previous_hashes": previous,
            "last_used_at": now,
            "idle_expires_at": now + IDLE_TIMEOUT,
        }},
    )
    session.update({"refresh_hash": hash_token(new_refresh), "last_used_at": now})
    return session, new_refresh, None


async def revoke_session(db, session_id: str, reason: str = "signed_out") -> None:
    await db[SESSIONS].update_one(
        {"session_id": session_id, "revoked_at": None},
        {"$set": {"revoked_at": _now(), "revoked_reason": reason}},
    )


async def revoke_all(db, user_id: str, except_session_id: Optional[str] = None, reason: str = "signed_out_everywhere") -> None:
    query: Dict[str, Any] = {"user_id": user_id, "revoked_at": None}
    if except_session_id:
        query["session_id"] = {"$ne": except_session_id}
    await db[SESSIONS].update_many(query, {"$set": {"revoked_at": _now(), "revoked_reason": reason}})


async def is_active(db, session_id: str) -> bool:
    """Used on each request. A session that was signed out stops working at once."""
    session = await db[SESSIONS].find_one({"session_id": session_id}, {"revoked_at": 1, "idle_expires_at": 1, "absolute_expires_at": 1})
    if session is None or session.get("revoked_at") is not None:
        return False
    now = _now()
    return now < _utc(session["idle_expires_at"]) and now < _utc(session["absolute_expires_at"])
