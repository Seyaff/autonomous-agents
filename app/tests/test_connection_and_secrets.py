"""Tests for token encryption, send-failure classification and menu chunking.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

import pytest
from cryptography.fernet import Fernet

from core import secrets as secrets_mod
from core.secrets import PREFIX, SecretError, protect, reveal
from core.settings import settings
from core.whatsapp_utils import SendResult
from services.menu_extraction import chunk_text


@pytest.fixture
def key(monkeypatch):
    k = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "TOKEN_ENCRYPTION_KEY", k)
    return k


def test_protect_then_reveal_round_trip(key):
    stored = protect("EAAG-secret-token")
    assert stored.startswith(PREFIX)
    assert "EAAG-secret-token" not in stored
    assert reveal(stored) == "EAAG-secret-token"


def test_plain_text_tokens_still_read(key):
    # Tokens saved before encryption existed are plain text and must keep working.
    assert reveal("EAAG-old-token") == "EAAG-old-token"


def test_empty_values_pass_through(key):
    assert protect(None) is None
    assert protect("") == ""
    assert reveal(None) is None


def test_encrypted_value_without_key_is_an_error(monkeypatch):
    monkeypatch.setattr(settings, "TOKEN_ENCRYPTION_KEY", "")
    with pytest.raises(SecretError):
        reveal(PREFIX + "abc")


def test_wrong_key_is_an_error(monkeypatch, key):
    stored = protect("EAAG-token")
    monkeypatch.setattr(settings, "TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    with pytest.raises(SecretError):
        reveal(stored)


def test_invalid_key_is_an_error(monkeypatch):
    monkeypatch.setattr(settings, "TOKEN_ENCRYPTION_KEY", "not-a-key")
    with pytest.raises(SecretError):
        protect("x")


def test_auth_errors_are_classified():
    assert SendResult(ok=False, status=401).auth_error
    assert SendResult(ok=False, status=400, error_code=190).auth_error
    assert SendResult(ok=False, status=400, error_code=131026).auth_error is False
    assert SendResult(ok=True, status=200).auth_error is False


def test_chunks_keep_paragraphs_whole_and_respect_size():
    paragraphs = [f"Dish {i} - {100 + i}" for i in range(400)]
    text = "\n\n".join(paragraphs)
    chunks = chunk_text(text, size=500)
    assert len(chunks) > 1
    assert all(len(c) <= 500 for c in chunks)
    # every dish name appears somewhere, and none is cut in half
    joined = "\n\n".join(chunks)
    for p in paragraphs:
        assert p in joined


def test_oversized_paragraph_is_split_hard():
    chunks = chunk_text("x" * 1200, size=500)
    assert [len(c) for c in chunks] == [500, 500, 200]


def test_empty_menu_has_no_chunks():
    assert chunk_text("   \n\n  ") == []
