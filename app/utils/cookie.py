from fastapi import Response
from core.settings import settings


def set_access_token_cookie(response: Response, token: str):
    # Set secure=True only in production (HTTPS), False in local development (HTTP)
    is_production = getattr(settings, "ENVIRONMENT", "development").lower() == "production"

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,           # Prevents JS XSS access
        secure=is_production,     # False on localhost so browser accepts cookie
        samesite="lax",          # Allows top-level OAuth redirects
        max_age=60 * 60 * 24 * 7, # 7 days
        path="/",
    )