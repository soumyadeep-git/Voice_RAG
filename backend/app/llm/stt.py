"""Speech-to-text via an OpenAI-compatible audio endpoint (Groq Whisper).

Kept separate from the chat LLM client: the answering model (Cerebras) does
not serve audio, so STT points at its own base URL / key.
"""

import threading
from typing import Optional

from openai import OpenAI

from app.config import get_settings

_client: Optional[OpenAI] = None
_lock = threading.Lock()


class STTUnavailableError(RuntimeError):
    pass


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                settings = get_settings()
                if not settings.stt_api_key:
                    raise STTUnavailableError("STT_API_KEY is not configured")
                _client = OpenAI(
                    base_url=settings.stt_base_url,
                    api_key=settings.stt_api_key,
                    timeout=60.0,
                )
    return _client


def transcribe(audio: bytes, filename: str = "audio.webm") -> str:
    settings = get_settings()
    resp = _get_client().audio.transcriptions.create(
        model=settings.stt_model,
        file=(filename, audio),
        response_format="text",
        # Pin English and use greedy decoding to avoid language drift
        # (e.g. spurious Portuguese) and reduce hallucinated filler on
        # short or near-silent clips.
        language="en",
        temperature=0.0,
    )
    text = resp if isinstance(resp, str) else getattr(resp, "text", "")
    return (text or "").strip()
