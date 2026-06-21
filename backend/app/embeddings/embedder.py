import threading
from typing import Optional

from fastembed import TextEmbedding

from app.config import get_settings

_model: Optional[TextEmbedding] = None
_lock = threading.Lock()


def get_embedder() -> TextEmbedding:
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                settings = get_settings()
                _model = TextEmbedding(model_name=settings.embed_model)
    return _model


def warm_up() -> None:
    embedder = get_embedder()
    list(embedder.embed(["warmup"]))


def embed_texts(texts: list[str]) -> list[list[float]]:
    embedder = get_embedder()
    return [vector.tolist() for vector in embedder.embed(texts)]


def embed_query(text: str) -> list[float]:
    embedder = get_embedder()
    return list(embedder.query_embed([text]))[0].tolist()
