from fastapi import Response
from core.settings import settings

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
# The refresh cookie is only sent to the auth routes, and SameSite=Lax keeps it off
# cross-site requests. The app reaches the API through its own /api proxy, so the path is /api/auth.
REFRESH_PATH = "/api/auth"
ACCESS_MAX_AGE = 60 * 15
REFRESH_MAX_AGE = 60 * 60 * 24 * 30


def set_access_token_cookie(response: Response, token: str):
    """Access cookie for the whole app. Cross-origin safe: SameSite=None with Secure."""
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=ACCESS_MAX_AGE,
        path="/",
    )


def set_refresh_token_cookie(response: Response, token: str):
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=REFRESH_MAX_AGE,
        path=REFRESH_PATH,
    )


def clear_access_token_cookie(response: Response):
    """Clear the access token cookie."""
    response.set_cookie(
        key=ACCESS_COOKIE,
        value="",
        httponly=True,
        secure=True,
        samesite="none",
        max_age=0,
        path="/",
    )


def clear_refresh_token_cookie(response: Response):
    response.set_cookie(
        key=REFRESH_COOKIE,
        value="",
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=0,
        path=REFRESH_PATH,
    )
