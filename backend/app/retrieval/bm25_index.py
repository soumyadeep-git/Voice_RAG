import re
import threading

from rank_bm25 import BM25Okapi

from app.retrieval import state
from app.store import repository

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class _Bm25Index:
    def __init__(self) -> None:
        self._bm25 = None
        self._chunks: list[dict] = []
        self._version = -1
        self._lock = threading.Lock()

    def _ensure(self) -> None:
        if self._version == state.current() and self._bm25 is not None:
            return
        with self._lock:
            if self._version == state.current() and self._bm25 is not None:
                return
            chunks = repository.get_all_chunks()
            corpus = [tokenize(c["text"]) for c in chunks]
            self._chunks = chunks
            self._bm25 = BM25Okapi(corpus) if corpus else None
            self._version = state.current()

    def search(self, query: str, k: int) -> list[tuple[dict, float]]:
        self._ensure()
        if not self._bm25 or not self._chunks:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [(self._chunks[i], float(scores[i])) for i in ranked if scores[i] > 0]


_index = _Bm25Index()


def search(query: str, k: int) -> list[tuple[dict, float]]:
    return _index.search(query, k)
