"""
Turns a customer's WhatsApp voice note into text.

Uses Whisper through the same provider as the agent: Groq in dev, OpenAI in prod.
Urdu is set as the spoken language. Whisper writes Urdu script, and the agent
replies in the same script the customer used.
"""

import logging
from typing import Tuple

import httpx

from core.settings import settings

logger = logging.getLogger(__name__)

URDU = "ur"


class TranscriptionError(Exception):
    pass


def _target() -> Tuple[str, str, str]:
    """(url, api key, model) for the active provider."""
    if (settings.LLM_PROVIDER or "groq").lower() == "openai":
        return (
            "https://api.openai.com/v1/audio/transcriptions",
            settings.OPENAI_API_KEY,
            settings.TRANSCRIBE_OPENAI_MODEL,
        )
    return (
        "https://api.groq.com/openai/v1/audio/transcriptions",
        settings.GROQ_API_KEY,
        settings.TRANSCRIBE_GROQ_MODEL,
    )


async def transcribe_urdu_audio(audio: bytes, filename: str = "voice.ogg") -> str:
    """Returns the transcript. Raises TranscriptionError if the provider refuses or fails."""
    url, key, model = _target()
    if not key:
        raise TranscriptionError("No API key set for transcription.")

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {key}"},
                data={"model": model, "language": URDU, "response_format": "json"},
                files={"file": (filename, audio, "audio/ogg")},
            )
        except httpx.RequestError as e:
            raise TranscriptionError(f"Could not reach the transcription service: {e}") from e

    if resp.status_code != 200:
        logger.error(f"Transcription failed ({resp.status_code}): {resp.text[:300]}")
        raise TranscriptionError(f"Transcription returned {resp.status_code}.")
    return (resp.json().get("text") or "").strip()
