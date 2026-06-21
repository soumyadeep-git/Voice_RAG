import uuid

from app.embeddings.embedder import embed_texts
from app.ingestion.chunk import chunk_segments
from app.ingestion.parse import parse_document
from app.store import repository, vector_store

EMBED_BATCH = 64


def ingest_document(doc_id: str, raw: bytes, filename: str) -> None:
    try:
        repository.set_document_status(doc_id, "processing")
        segments = parse_document(raw, filename)
        chunks = chunk_segments(segments)
        if not chunks:
            repository.set_document_status(doc_id, "failed", "No chunks produced")
            return

        rows: list[dict] = []
        ids: list[str] = []
        texts: list[str] = []
        metadatas: list[dict] = []
        for ordinal, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}:{ordinal}"
            ids.append(chunk_id)
            texts.append(chunk.text)
            metadatas.append(
                {
                    "document_id": doc_id,
                    "filename": filename,
                    "ordinal": ordinal,
                    "page": chunk.page if chunk.page is not None else -1,
                    "section": chunk.section or "",
                }
            )
            rows.append(
                {
                    "id": chunk_id,
                    "document_id": doc_id,
                    "ordinal": ordinal,
                    "text": chunk.text,
                    "page": chunk.page,
                    "section": chunk.section,
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                }
            )

        embeddings: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH):
            embeddings.extend(embed_texts(texts[start : start + EMBED_BATCH]))

        repository.insert_chunks(rows)
        vector_store.add_chunks(ids, embeddings, texts, metadatas)
        repository.set_document_chunks(doc_id, len(chunks))
    except Exception as exc:
        repository.set_document_status(doc_id, "failed", str(exc)[:500])


def new_document_id() -> str:
    return uuid.uuid4().hex
