import os
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Provider-agnostic LLM config. Any OpenAI-compatible endpoint works
    # (Groq, Cerebras, OpenRouter, Together, local Ollama, ...) by setting
    # LLM_BASE_URL + LLM_API_KEY. Legacy GROQ_* / CEREBRAS_API_KEY names are
    # still accepted so existing .env files keep working.
    llm_provider: str = Field(default="cerebras", validation_alias=AliasChoices("LLM_PROVIDER"))
    llm_base_url: str = Field(
        default="https://api.cerebras.ai/v1",
        validation_alias=AliasChoices("LLM_BASE_URL"),
    )
    llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_API_KEY", "CEREBRAS_API_KEY", "GROQ_API_KEY"),
    )
    answer_model: str = Field(
        default="gpt-oss-120b",
        validation_alias=AliasChoices("ANSWER_MODEL", "GROQ_ANSWER_MODEL"),
    )
    fast_model: str = Field(
        default="gpt-oss-120b",
        validation_alias=AliasChoices("FAST_MODEL", "GROQ_FAST_MODEL"),
    )
    # Speech-to-text runs on a separate OpenAI-compatible endpoint (Groq Whisper
    # by default) since the chat provider (e.g. Cerebras) may not serve audio.
    stt_base_url: str = Field(
        default="https://api.groq.com/openai/v1",
        validation_alias=AliasChoices("STT_BASE_URL"),
    )
    stt_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("STT_API_KEY", "GROQ_API_KEY"),
    )
    stt_model: str = Field(
        default="whisper-large-v3-turbo",
        validation_alias=AliasChoices("STT_MODEL", "GROQ_STT_MODEL"),
    )

    # Text-to-speech via Cartesia (natural voices). Leave the key empty to fall
    # back to the browser's built-in speechSynthesis. If no voice id is set, a
    # female English voice is auto-selected from the account's voice library.
    cartesia_api_key: str = Field(default="", validation_alias=AliasChoices("CARTESIA_API_KEY"))
    cartesia_model: str = Field(default="sonic-2", validation_alias=AliasChoices("CARTESIA_MODEL"))
    cartesia_voice_id: str = Field(default="", validation_alias=AliasChoices("CARTESIA_VOICE_ID"))
    cartesia_version: str = Field(
        default="2025-11-04", validation_alias=AliasChoices("CARTESIA_VERSION")
    )

    embed_model: str = "BAAI/bge-small-en-v1.5"

    retrieval_candidates: int = 20
    retrieval_top_k: int = 5
    enable_rerank: bool = True
    rerank_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"

    data_dir: str = "data"
    chroma_dir: str = "storage/chroma"
    sqlite_path: str = "storage/app.sqlite"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def data_path(self) -> Path:
        return self._resolve(self.data_dir)

    @property
    def chroma_path(self) -> Path:
        return self._resolve(self.chroma_dir)

    @property
    def sqlite_file(self) -> Path:
        return self._resolve(self.sqlite_path)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def _resolve(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else BACKEND_ROOT / path


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_path.mkdir(parents=True, exist_ok=True)
    settings.chroma_path.mkdir(parents=True, exist_ok=True)
    settings.sqlite_file.parent.mkdir(parents=True, exist_ok=True)
    return settings
