import threading
from collections import OrderedDict
from typing import Optional

from app.retrieval import state

_cache: "OrderedDict[tuple, list[dict]]" = OrderedDict()
_lock = threading.Lock()
_MAX_ENTRIES = 256


def _key(query: str, top_k: int, use_rerank: bool) -> tuple:
    return (state.current(), query.strip().lower(), top_k, use_rerank)


def get(query: str, top_k: int, use_rerank: bool) -> Optional[list[dict]]:
    key = _key(query, top_k, use_rerank)
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    return None


def put(query: str, top_k: int, use_rerank: bool, value: list[dict]) -> None:
    key = _key(query, top_k, use_rerank)
    with _lock:
        _cache[key] = value
        _cache.move_to_end(key)
        while len(_cache) > _MAX_ENTRIES:
            _cache.popitem(last=False)
