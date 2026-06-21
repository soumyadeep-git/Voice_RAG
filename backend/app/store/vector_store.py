import logging
import threading
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import get_settings

logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)

_client: Optional[chromadb.ClientAPI] = None
_lock = threading.Lock()
COLLECTION = "chunks"


def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                settings = get_settings()
                _client = chromadb.PersistentClient(
                    path=str(settings.chroma_path),
                    settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
                )
    return _client


def _collection():
    return _get_client().get_or_create_collection(
        name=COLLECTION, metadata={"hnsw:space": "cosine"}
    )


def add_chunks(
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict],
) -> None:
    if not ids:
        return
    _collection().add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)


def query(embedding: list[float], n_results: int) -> list[dict]:
    collection = _collection()
    count = collection.count()
    if count == 0:
        return []
    result = collection.query(
        query_embeddings=[embedding],
        n_results=min(n_results, count),
        include=["documents", "metadatas", "distances"],
    )
    hits: list[dict] = []
    for cid, doc, meta, dist in zip(
        result["ids"][0],
        result["documents"][0],
        result["metadatas"][0],
        result["distances"][0],
    ):
        hits.append({"id": cid, "text": doc, "metadata": meta, "distance": dist})
    return hits


def delete_document(doc_id: str) -> None:
    _collection().delete(where={"document_id": doc_id})


def count() -> int:
    return _collection().count()
