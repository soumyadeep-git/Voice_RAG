from typing import Optional

from fastapi import APIRouter, Query

from app.retrieval.service import retrieve

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def search(
    q: str = Query(..., min_length=1),
    top_k: Optional[int] = None,
    rerank: Optional[bool] = None,
) -> dict:
    results = retrieve(q, top_k=top_k, use_rerank=rerank)
    return {"query": q, "results": results}
