"""Voice notes: which Whisper endpoint is used, and the fallback when transcription fails.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

import asyncio

import pytest

from core import settings as settings_module
from services import voice_transcription
from services.voice_transcription import TranscriptionError, _target


def test_dev_uses_groq_whisper(monkeypatch):
    monkeypatch.setattr(settings_module.settings, "LLM_PROVIDER", "groq")
    url, _, model = _target()
    assert url == "https://api.groq.com/openai/v1/audio/transcriptions"
    assert model == settings_module.settings.TRANSCRIBE_GROQ_MODEL


def test_prod_uses_openai_whisper(monkeypatch):
    monkeypatch.setattr(settings_module.settings, "LLM_PROVIDER", "openai")
    url, _, model = _target()
    assert url == "https://api.openai.com/v1/audio/transcriptions"
    assert model == settings_module.settings.TRANSCRIBE_OPENAI_MODEL


def test_missing_key_is_a_transcription_error(monkeypatch):
    monkeypatch.setattr(settings_module.settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(settings_module.settings, "GROQ_API_KEY", "")
    with pytest.raises(TranscriptionError):
        asyncio.run(voice_transcription.transcribe_urdu_audio(b"not really audio"))
