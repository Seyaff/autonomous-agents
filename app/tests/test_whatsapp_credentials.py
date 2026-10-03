"""Each restaurant uses only its own WhatsApp credentials. Nothing falls back to .env.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

import asyncio

from core import whatsapp_utils
from core.whatsapp_utils import NOT_CONNECTED, resolve_tenant_whatsapp_credentials, send_buttons, send_text


def test_unconnected_restaurant_gets_no_credentials(monkeypatch):
    monkeypatch.setattr(whatsapp_utils.settings, "WHATSAPP_TOKEN", "env-token")
    monkeypatch.setattr(whatsapp_utils.settings, "WHATSAPP_PHONE_NUMBER_ID", "env-phone")
    token, phone = resolve_tenant_whatsapp_credentials({"tenant_id": "new_owner"})
    assert token is None and phone is None


def test_send_text_refuses_without_own_credentials(monkeypatch):
    monkeypatch.setattr(whatsapp_utils.settings, "WHATSAPP_TOKEN", "env-token")
    monkeypatch.setattr(whatsapp_utils.settings, "WHATSAPP_PHONE_NUMBER_ID", "env-phone")
    result = asyncio.run(send_text(to_phone="923001234567", text="hi", token=None, phone_number_id=None))
    assert not result.ok
    assert result.error_message == NOT_CONNECTED


def test_send_buttons_refuses_without_own_credentials(monkeypatch):
    monkeypatch.setattr(whatsapp_utils.settings, "WHATSAPP_TOKEN", "env-token")
    result = asyncio.run(send_buttons(to_phone="923001234567", body="x", buttons=[{"id": "a", "title": "A"}]))
    assert not result.ok
    assert result.error_message == NOT_CONNECTED


def test_connected_restaurant_uses_its_own_credentials():
    token, phone = resolve_tenant_whatsapp_credentials({"phone_number_id": "own-phone", "whatsapp_access_token": None})
    assert phone == "own-phone"
    assert token is None  # no token stored, so nothing is used
