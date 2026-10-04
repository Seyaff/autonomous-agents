from typing import Optional

import jwt
from fastapi import Request, Depends, HTTPException, status

from core.database import get_database
from utils.jwt import verify_access_claims
from services.sessions import is_active


async def _resolve_user_from_token(token: Optional[str], database) -> dict:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated (missing cookie)",
        )

    try:
        claims = verify_access_claims(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    # A token from a session that was signed out stops working at once. Tokens issued
    # before sessions existed have no session id, and keep working until they expire.
    session_id = claims.get("sid")
    if session_id and not await is_active(database, session_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ended. Please sign in again.",
        )

    user_id = claims["sub"]
    user = await database["users"].find_one({"user_id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if "_id" in user:
        user["_id"] = str(user["_id"])

    return user


async def get_current_user(request: Request, database=Depends(get_database)) -> dict:
    """Authenticates any signed-in user (FOUNDER or OWNER), no role check."""
    token = request.cookies.get("access_token")
    return await _resolve_user_from_token(token, database)


async def require_owner_role(request: Request, database=Depends(get_database)) -> dict:
    """Authenticates the caller and requires role == OWNER — no tenant
    required yet. Use this (not require_owner) for onboarding routes like
    tenant creation, where the caller doesn't have a tenant until the route
    runs."""
    user = await get_current_user(request, database)
    if user.get("role") != "OWNER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner access required.",
        )
    return user


async def require_owner(request: Request, database=Depends(get_database)) -> dict:
    """
    Authenticates the caller, requires role == OWNER, and requires an
    active tenant — the combination every restaurant-owner-scoped route
    (orders, analytics, inbox, knowledge, tenant settings) needs.
    """
    user = await require_owner_role(request, database)
    if not user.get("active_tenant_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active tenant linked to your account. Please complete onboarding.",
        )
    return user


async def require_founder(request: Request, database=Depends(get_database)) -> dict:
    """Authenticates the caller and requires role == FOUNDER."""
    user = await get_current_user(request, database)
    if user.get("role") != "FOUNDER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Founder access required.",
        )
    return user


async def get_current_user_ws(websocket, database) -> Optional[dict]:
    """
    Websocket variant of get_current_user — reads the access_token cookie
    off the handshake request instead of an HTTP Request. Returns None
    (never raises) so callers can close the socket with a clean code.
    """
    token = websocket.cookies.get("access_token")
    if not token:
        return None
    try:
        return await _resolve_user_from_token(token, database)
    except HTTPException:
        return None
