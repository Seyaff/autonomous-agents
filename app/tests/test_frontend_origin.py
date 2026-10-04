"""Where users are sent after sign-in: the app's own address, never localhost in production.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

from core.settings import Settings


def test_production_falls_back_to_the_callback_site_when_frontend_url_is_missing():
    s = Settings(FRONTEND_URL="http://localhost:3000", GOOGLE_CALLBACK_URL="https://siyaf.vercel.app/api/auth/google/callback")
    assert s.frontend_origin == "https://siyaf.vercel.app"


def test_a_configured_frontend_url_wins():
    s = Settings(FRONTEND_URL="https://app.example.com/", GOOGLE_CALLBACK_URL="https://siyaf.vercel.app/api/auth/google/callback")
    assert s.frontend_origin == "https://app.example.com"


def test_local_development_stays_on_localhost():
    s = Settings(FRONTEND_URL="http://localhost:3000", GOOGLE_CALLBACK_URL="http://localhost:8000/api/v1/auth/google/callback")
    assert s.frontend_origin == "http://localhost:3000"


def test_the_frontend_origin_variable_name_is_accepted(monkeypatch):
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://siyaf.vercel.app")
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    assert Settings().FRONTEND_URL == "https://siyaf.vercel.app"
