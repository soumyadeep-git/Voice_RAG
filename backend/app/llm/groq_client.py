import threading
from typing import Iterator, Optional

from groq import (
    APIConnectionError,
    APITimeoutError,
    Groq,
    InternalServerError,
    RateLimitError,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings

_client: Optional[Groq] = None
_lock = threading.Lock()

_RETRYABLE = (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError)


class LLMUnavailableError(RuntimeError):
    pass


def _get_client() -> Groq:
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                settings = get_settings()
                if not settings.groq_api_key:
                    raise LLMUnavailableError("GROQ_API_KEY is not configured")
                _client = Groq(api_key=settings.groq_api_key, timeout=30.0)
    return _client


@retry(
    retry=retry_if_exception_type(_RETRYABLE),
    wait=wait_exponential(multiplier=1, min=1, max=20),
    stop=stop_after_attempt(4),
    reraise=True,
)
def chat(
    messages: list[dict],
    model: Optional[str] = None,
    tools: Optional[list[dict]] = None,
    tool_choice: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 1024,
):
    settings = get_settings()
    kwargs: dict = {
        "model": model or settings.groq_answer_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice or "auto"
    return _get_client().chat.completions.create(**kwargs)


def complete_text(
    system: str,
    user: str,
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 256,
) -> str:
    resp = chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return (resp.choices[0].message.content or "").strip()


@retry(
    retry=retry_if_exception_type(_RETRYABLE),
    wait=wait_exponential(multiplier=1, min=1, max=20),
    stop=stop_after_attempt(4),
    reraise=True,
)
def stream_chat(
    messages: list[dict],
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> Iterator[str]:
    settings = get_settings()
    stream = _get_client().chat.completions.create(
        model=model or settings.groq_answer_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
