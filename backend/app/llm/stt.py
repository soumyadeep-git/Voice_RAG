"""Speech-to-text via an OpenAI-compatible audio endpoint (Groq Whisper).

Kept separate from the chat LLM client: the answering model (Cerebras) does
not serve audio, so STT points at its own base URL / key.
"""

import re
import threading
from collections import Counter
from typing import Optional

from openai import OpenAI

from app.config import get_settings
from app.store import repository

_client: Optional[OpenAI] = None
_lock = threading.Lock()

# Cache the biasing prompt; rebuild only when the corpus size changes.
_vocab_cache: dict = {"key": None, "prompt": ""}
_MAX_TERMS = 40
_MAX_PROMPT_CHARS = 600


class STTUnavailableError(RuntimeError):
    pass


def _filename_tokens(docs: list[dict]) -> list[str]:
    words: list[str] = []
    for d in docs:
        name = re.sub(r"\.[A-Za-z0-9]+$", "", d.get("filename", "") or "")
        for w in re.split(r"[^A-Za-z0-9]+", name):
            if len(w) >= 3:
                words.append(w.lower())
    return words


def _corpus_terms(chunks: list[dict]) -> tuple[list[str], list[str]]:
    """Mine the strongest spelling cues from the corpus: acronyms (GDPR, CCPA)
    and capitalized multi-word phrases (e.g. "Data Protection")."""
    acronyms: Counter = Counter()
    phrases: Counter = Counter()
    for c in chunks:
        text = c.get("text", "") or ""
        for m in re.findall(r"\b[A-Z]{2,6}\b", text):
            acronyms[m] += 1
        for m in re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}\b", text):
            phrases[m] += 1
    top_acr = [w for w, _ in acronyms.most_common(15)]
    top_phrases = [w for w, _ in phrases.most_common(15)]
    return top_acr, top_phrases


def build_vocab_prompt() -> str:
    """A short biasing prompt of domain terms so Whisper spells them correctly.
    Derived from the uploaded corpus, so it adapts to any document set."""
    try:
        chunks = repository.get_all_chunks()
    except Exception:
        return ""
    key = len(chunks)
    if _vocab_cache["key"] == key:
        return _vocab_cache["prompt"]

    acr, phrases = _corpus_terms(chunks)
    try:
        fnames = _filename_tokens(repository.list_documents())
    except Exception:
        fnames = []

    terms: list[str] = []
    for t in [*acr, *phrases, *fnames]:
        if t and t not in terms:
            terms.append(t)
    terms = terms[:_MAX_TERMS]

    prompt = (
        "Questions about the user's documents. Likely terms: " + ", ".join(terms) + "."
        if terms
        else ""
    )[:_MAX_PROMPT_CHARS]

    _vocab_cache["key"] = key
    _vocab_cache["prompt"] = prompt
    return prompt


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
    kwargs: dict = dict(
        model=settings.stt_model,
        file=(filename, audio),
        response_format="text",
        # Pin English and use greedy decoding to avoid language drift
        # (e.g. spurious Portuguese) and reduce hallucinated filler on
        # short or near-silent clips.
        language="en",
        temperature=0.0,
    )
    # Bias decoding toward the corpus' domain vocabulary so acronyms and proper
    # terms (GDPR, CCPA, ...) are spelled right instead of mis-heard.
    prompt = build_vocab_prompt()
    if prompt:
        kwargs["prompt"] = prompt

    resp = _get_client().audio.transcriptions.create(**kwargs)
    text = resp if isinstance(resp, str) else getattr(resp, "text", "")
    return (text or "").strip()
