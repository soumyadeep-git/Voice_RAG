import threading

from app.config import get_settings

_model = None
_lock = threading.Lock()
_available = True


def _get_model():
    global _model, _available
    if _model is None and _available:
        with _lock:
            if _model is None and _available:
                try:
                    from fastembed.rerank.cross_encoder import TextCrossEncoder

                    _model = TextCrossEncoder(model_name=get_settings().rerank_model)
                except Exception:
                    _available = False
    return _model


def warm_up() -> None:
    model = _get_model()
    if model:
        try:
            list(model.rerank("warmup", ["warmup passage"]))
        except Exception:
            pass


def rerank(query: str, passages: list[dict]) -> list[dict]:
    model = _get_model()
    if not model or not passages:
        return passages
    try:
        scores = list(model.rerank(query, [p["text"] for p in passages]))
    except Exception:
        return passages
    order = sorted(range(len(passages)), key=lambda i: scores[i], reverse=True)
    ranked = []
    for rank, i in enumerate(order):
        passage = dict(passages[i])
        passage["rerank_score"] = float(scores[i])
        ranked.append(passage)
    return ranked
