import re
import logging
from typing import Optional, Tuple
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

# Pashto phonetic number mapping to standard numerals
PASHTO_NUMBERS = {
    r"\b(yao|yaw|yo)\b": "1",
    r"\b(dwa|dawa|duwa)\b": "2",
    r"\b(dray|dre|dree)\b": "3",
    r"\b(salor|tsalor|salwar|char)\b": "4",
    r"\b(peenzah|pinza|penza)\b": "5",
    r"\b(shpag|shpa|shpagh)\b": "6",
    r"\b(oowah|oowa|awa)\b": "7",
    r"\b(atah|ata)\b": "8",
    r"\b(nah|naha)\b": "9",
    r"\b(las|lass)\b": "10",
}

# Common Pashto colloquial terms mapped to Roman Urdu equivalents
PASHTO_PHRASES = {
    r"\bra[- ]?ulighawa\b": "bhej dein",
    r"\brawalege\b": "bhej dein",
    r"\bdagha\b": "yeh",
    r"\bkhurak\b": "portion / plate",
    r"\bnaana\b": "naan",
    r"\bchaye\b": "kahwa",
    r"\bpaise\b": "rupaye",
}

DEFAULT_ASR_PROMPT = (
    "Pakistani restaurant food order in Roman Urdu and Pashto: "
    "Shinwari Mutton Karahi, Peshawari Chapli Kabab, Kabuli Pulao, Roghani Naan, Peshawari Kahwa. "
    "Yao, Dwa, Dray, Salor, Peenzah, Shpag. Cash on delivery, address, parcel."
)

class AudioService:
    def __init__(self):
        self.groq_api_key = settings.GROQ_API_KEY
        self.fish_audio_api_key = getattr(settings, "FISH_AUDIO_API_KEY", None)

    def normalize_pashto_urdu_transcript(self, raw_transcript: str) -> str:
        """
        Normalizes transcribed audio text:
        - Resolves phonetic Pashto numbers into Arabic numerals (e.g. 'yao karahi ao salor naana' -> '1 karahi ao 4 naan')
        - Standardizes colloquial ordering terms
        """
        if not raw_transcript:
            return ""

        text = raw_transcript.strip()

        # Replace Pashto numbers (case-insensitive)
        for pattern, replacement in PASHTO_NUMBERS.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # Standardize common ordering constructs
        for pattern, replacement in PASHTO_PHRASES.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        return text.strip()

    async def transcribe_voice_note(
        self,
        audio_bytes: bytes,
        filename: str = "voice_note.ogg",
        mime_type: str = "audio/ogg"
    ) -> Tuple[str, str]:
        """
        Transcribes voice note using Fish Audio ASR or Groq Whisper Large v3.
        Returns: (raw_transcript, normalized_transcript)
        """
        if not audio_bytes:
            return "", ""

        # Strategy A: Fish Audio ASR if configured
        if self.fish_audio_api_key:
            try:
                logger.info("Transcribing audio via Fish Audio ASR (transcribe-1-pro)...")
                async with httpx.AsyncClient(timeout=25.0) as client:
                    files = {"file": (filename, audio_bytes, mime_type)}
                    headers = {"Authorization": f"Bearer {self.fish_audio_api_key}"}
                    data = {"model": "transcribe-1-pro", "language": "ur"}
                    resp = await client.post("https://api.fish.audio/v1/asr", headers=headers, files=files, data=data)
                    if resp.status_code == 200:
                        raw_text = resp.json().get("text", "")
                        normalized = self.normalize_pashto_urdu_transcript(raw_text)
                        return raw_text, normalized
                    else:
                        logger.warning(f"Fish Audio ASR returned {resp.status_code}, falling back to Groq: {resp.text}")
            except Exception as e:
                logger.error(f"Fish Audio ASR failed: {e}. Falling back to Groq Whisper.")

        # Strategy B: Groq Whisper Large v3 (sub-350ms ultra-fast ASR)
        try:
            logger.info("Transcribing audio via Groq Whisper Large v3...")
            async with httpx.AsyncClient(timeout=20.0) as client:
                files = {"file": (filename, audio_bytes, mime_type)}
                headers = {"Authorization": f"Bearer {self.groq_api_key}"}
                data = {
                    "model": "whisper-large-v3",
                    "prompt": DEFAULT_ASR_PROMPT,
                    "response_format": "json",
                    "temperature": 0.0,
                }
                resp = await client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers=headers,
                    files=files,
                    data=data
                )
                if resp.status_code == 200:
                    raw_text = resp.json().get("text", "").strip()
                    normalized = self.normalize_pashto_urdu_transcript(raw_text)
                    logger.info(f"Groq Whisper raw transcript: '{raw_text}' -> normalized: '{normalized}'")
                    return raw_text, normalized
                else:
                    logger.error(f"Groq Whisper returned {resp.status_code}: {resp.text}")
                    return "", ""
        except Exception as ex:
            logger.error(f"Groq Whisper transcription exception: {ex}")
            return "", ""

audio_service = AudioService()
