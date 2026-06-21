import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.embeddings.embedder import warm_up
from app.routes import documents
from app.store import vector_store
from app.store.db import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    threading.Thread(target=warm_up, daemon=True).start()
    yield


app = FastAPI(title="Ask My Notes", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "answer_model": settings.groq_answer_model,
        "embed_model": settings.embed_model,
        "groq_key_present": bool(settings.groq_api_key),
        "indexed_chunks": vector_store.count(),
    }
