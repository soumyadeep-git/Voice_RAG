import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.embeddings.embedder import warm_up as warm_embedder
from app.retrieval.rerank import warm_up as warm_reranker
from app.routes import ask, conversations, documents, search, transcribe, tts, voice_ws
from app.store import vector_store
from app.store.db import init_db

settings = get_settings()


def _warm_models() -> None:
    warm_embedder()
    if settings.enable_rerank:
        warm_reranker()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    threading.Thread(target=_warm_models, daemon=True).start()
    yield


app = FastAPI(title="Ask My Notes", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(documents.router)
app.include_router(search.router)
app.include_router(ask.router)
app.include_router(conversations.router)
app.include_router(transcribe.router)
app.include_router(tts.router)
app.include_router(voice_ws.router)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "provider": settings.llm_provider,
        "answer_model": settings.answer_model,
        "embed_model": settings.embed_model,
        "llm_key_present": bool(settings.llm_api_key),
        "indexed_chunks": vector_store.count(),
    }
