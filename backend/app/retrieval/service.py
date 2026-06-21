from typing import Optional

from app.config import get_settings
from app.embeddings.embedder import embed_query
from app.retrieval import bm25_index, cache
from app.retrieval import rerank as rerank_mod
from app.store import vector_store

RRF_K = 60


def retrieve(
    query: str,
    top_k: Optional[int] = None,
    candidates: Optional[int] = None,
    use_rerank: Optional[bool] = None,
) -> list[dict]:
    settings = get_settings()
    top_k = top_k or settings.retrieval_top_k
    candidates = candidates or settings.retrieval_candidates
    use_rerank = settings.enable_rerank if use_rerank is None else use_rerank

    query = (query or "").strip()
    if not query:
        return []

    cached = cache.get(query, top_k, use_rerank)
    if cached is not None:
        return cached

    dense_hits = vector_store.query(embed_query(query), candidates)
    sparse_hits = bm25_index.search(query, candidates)

    pool: dict[str, dict] = {}
    dense_order: list[str] = []
    for hit in dense_hits:
        meta = hit["metadata"]
        pool[hit["id"]] = {
            "id": hit["id"],
            "text": hit["text"],
            "document_id": meta.get("document_id"),
            "filename": meta.get("filename"),
            "page": _clean_page(meta.get("page")),
            "section": (meta.get("section") or None),
            "vector_distance": hit.get("distance"),
        }
        dense_order.append(hit["id"])

    sparse_order: list[str] = []
    for chunk, _score in sparse_hits:
        cid = chunk["id"]
        sparse_order.append(cid)
        if cid not in pool:
            pool[cid] = {
                "id": cid,
                "text": chunk["text"],
                "document_id": chunk["document_id"],
                "filename": chunk["filename"],
                "page": _clean_page(chunk.get("page")),
                "section": (chunk.get("section") or None),
                "vector_distance": None,
            }

    fused = _reciprocal_rank_fusion([dense_order, sparse_order])
    ranked = sorted(pool.values(), key=lambda p: fused.get(p["id"], 0.0), reverse=True)
    for passage in ranked:
        passage["fusion_score"] = fused.get(passage["id"], 0.0)

    shortlist = ranked[:candidates]
    if use_rerank:
        shortlist = rerank_mod.rerank(query, shortlist)

    results = shortlist[:top_k]
    cache.put(query, top_k, use_rerank, results)
    return results


def _reciprocal_rank_fusion(rankings: list[list[str]]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, cid in enumerate(ranking):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank + 1)
    return scores


def _clean_page(page) -> Optional[int]:
    if page is None or page == -1:
        return None
    return page
