"""Text-to-speech via Cartesia (natural, low-latency voices).

Exposes a single `synthesize(text) -> mp3 bytes`. If no voice id is configured,
a female English voice is resolved once from the account's voice library and
cached. Raises TTSUnavailableError when no API key is set so callers can fall
back to the browser voice.
"""

import threading
from typing import Optional

import httpx

from app.config import get_settings

BASE_URL = "https://api.cartesia.ai"

_voice_id: Optional[str] = None
_lock = threading.Lock()


class TTSUnavailableError(RuntimeError):
    pass


def _headers() -> dict:
    settings = get_settings()
    return {
        "X-API-Key": settings.cartesia_api_key,
        "Cartesia-Version": settings.cartesia_version,
        "Content-Type": "application/json",
    }


def _resolve_voice_id() -> str:
    global _voice_id
    settings = get_settings()
    if settings.cartesia_voice_id:
        return settings.cartesia_voice_id
    if _voice_id:
        return _voice_id
    with _lock:
        if _voice_id:
            return _voice_id
        resp = httpx.get(
            f"{BASE_URL}/voices",
            headers=_headers(),
            params={"limit": 100},
            timeout=30.0,
        )
        resp.raise_for_status()
        body = resp.json()
        voices = body.get("data", body) if isinstance(body, dict) else body
        voices = voices or []

        def is_english(v: dict) -> bool:
            return (v.get("language") or "").lower().startswith("en")

        def is_female(v: dict) -> bool:
            return "fem" in (v.get("gender") or "").lower()

        pick = (
            next((v for v in voices if is_english(v) and is_female(v)), None)
            or next((v for v in voices if is_english(v)), None)
            or (voices[0] if voices else None)
        )
        if not pick or not pick.get("id"):
            raise TTSUnavailableError("no Cartesia voice available")
        _voice_id = pick["id"]
        return _voice_id


def synthesize(text: str) -> bytes:
    settings = get_settings()
    if not settings.cartesia_api_key:
        raise TTSUnavailableError("CARTESIA_API_KEY is not configured")

    payload = {
        "model_id": settings.cartesia_model,
        "transcript": text,
        "voice": {"mode": "id", "id": _resolve_voice_id()},
        "language": "en",
        "output_format": {"container": "mp3", "bit_rate": 128000, "sample_rate": 44100},
    }
    resp = httpx.post(
        f"{BASE_URL}/tts/bytes",
        headers=_headers(),
        json=payload,
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.content
