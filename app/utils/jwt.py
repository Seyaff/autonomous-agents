from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from fastapi import HTTPException, status
from core.settings import settings

# Short on purpose. The refresh cookie renews it, and a signed-out session stops working
# on the next request, so a copied token is only useful for this window.
ACCESS_TOKEN_MINUTES = 15


def generate_access_token(user_id: str, session_id: Optional[str] = None) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
        "iss": "Siyaf",
        "type": "access",
    }
    if session_id:
        payload["sid"] = session_id

    token = jwt.encode(
        payload,
        key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    return token


def verify_access_claims(token: str) -> Dict[str, Any]:
    """Checks the signature and expiry. Returns the claims."""
    payload = jwt.decode(
        token,
        key=settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    if not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    return payload


def verify_jwt_token(token: str):
    user_id: str = verify_access_claims(token)["sub"]
    return user_id
