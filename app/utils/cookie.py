from fastapi import Response
from core.settings import settings


def set_access_token_cookie(response: Response, token: str):
    """
    Set access token cookie for cross-origin (Vercel frontend → Render backend).
    
    For cross-origin cookies (Vercel HTTPS → Render HTTPS):
    - SameSite=None (allows cross-origin)
    - Secure=True (required for SameSite=None)
    - No domain restriction (allows all subdomains)
    """
    is_production = getattr(settings, "ENVIRONMENT", "development").lower() == "production"
    
    # For cross-origin, always use SameSite=None and Secure=True
    # On localhost, browser may reject but that's expected for local dev
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,           # Prevents JS XSS access
        secure=True,             # Required for SameSite=None
        samesite="none",         # Allows cross-origin (Vercel → Render)
        max_age=60 * 60 * 24 * 7, # 7 days
        path="/",
        # No domain= - allows all subdomains
    )


def clear_access_token_cookie(response: Response):
    """Clear the access token cookie."""
    response.set_cookie(
        key="access_token",
        value="",
        httponly=True,
        secure=True,
        samesite="none",
        max_age=0,
        path="/",
    )