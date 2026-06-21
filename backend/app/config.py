from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: str = ""
    groq_answer_model: str = "llama-3.3-70b-versatile"
    groq_fast_model: str = "llama-3.1-8b-instant"
    groq_stt_model: str = "whisper-large-v3-turbo"

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
