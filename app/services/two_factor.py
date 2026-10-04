"""
Two-step sign-in for owners (authenticator app codes and recovery codes).

The founder account doesn't use it. Login for an owner with it turned on doesn't start a
session. It returns a short-lived challenge instead, and the code from the authenticator
app (or a recovery code) completes the sign-in. Failed codes lock the account for a short time.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import bcrypt
import jwt
import pyotp

from core.settings import settings

ISSUER = "Siyaf"
CHALLENGE_MINUTES = 5
MAX_FAILED_CODES = 5
LOCK_MINUTES = 15
RECOVERY_CODE_COUNT = 8


def is_owner(user: Dict[str, Any]) -> bool:
    return user.get("role") == "OWNER"


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)


def verify_totp(secret: str, code: str) -> bool:
    code = (code or "").replace(" ", "").strip()
    if not code.isdigit() or len(code) != 6:
        return False
    # One step either side, to allow for clock drift between the phone and the server.
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def new_recovery_codes() -> List[str]:
    return [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}" for _ in range(RECOVERY_CODE_COUNT)]


def hash_recovery_codes(codes: List[str]) -> List[str]:
    return [bcrypt.hashpw(c.encode("utf-8"), bcrypt.gensalt()).decode("utf-8") for c in codes]


def use_recovery_code(stored_hashes: List[str], code: str) -> Optional[int]:
    """Index of the recovery code that matches (it can only be used once), or None."""
    cleaned = (code or "").strip().lower()
    for index, stored in enumerate(stored_hashes):
        if bcrypt.checkpw(cleaned.encode("utf-8"), stored.encode("utf-8")):
            return index
    return None


def is_locked(user: Dict[str, Any], now: Optional[datetime] = None) -> bool:
    until = user.get("totp_locked_until")
    if not until:
        return False
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    return (now or datetime.now(timezone.utc)) < until


def challenge_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "2fa",
        "iat": now,
        "exp": now + timedelta(minutes=CHALLENGE_MINUTES),
        "iss": "Siyaf",
    }
    return jwt.encode(payload, key=settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def read_challenge(token: str) -> Optional[str]:
    try:
        claims = jwt.decode(token, key=settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if claims.get("type") != "2fa":
        return None
    return claims.get("sub")
