from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile

from app.config import get_settings
from app.ingestion.service import ingest_document, new_document_id
from app.models import DocumentOut, UploadResult
from app.store import repository, vector_store

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_SUFFIXES = {".pdf", ".txt", ".md", ".markdown"}
MAX_BYTES = 25 * 1024 * 1024


@router.post("", response_model=UploadResult)
async def upload_documents(files: list[UploadFile], background: BackgroundTasks) -> UploadResult:
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    settings = get_settings()
    accepted: list[DocumentOut] = []
    rejected: list[dict] = []

    for file in files:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            rejected.append({"filename": file.filename, "reason": "unsupported file type"})
            continue

        raw = await file.read()
        if not raw:
            rejected.append({"filename": file.filename, "reason": "empty file"})
            continue
        if len(raw) > MAX_BYTES:
            rejected.append({"filename": file.filename, "reason": "file too large"})
            continue

        doc_id = new_document_id()
        (settings.data_path / f"{doc_id}{suffix}").write_bytes(raw)
        repository.create_document(doc_id, file.filename, file.content_type or "", len(raw))
        background.add_task(ingest_document, doc_id, raw, file.filename)
        accepted.append(DocumentOut(**repository.get_document(doc_id)))

    return UploadResult(accepted=accepted, rejected=rejected)


@router.get("", response_model=list[DocumentOut])
def list_documents() -> list[DocumentOut]:
    return [DocumentOut(**doc) for doc in repository.list_documents()]


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: str) -> DocumentOut:
    doc = repository.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentOut(**doc)


@router.delete("/{doc_id}")
def delete_document(doc_id: str) -> dict:
    doc = repository.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    vector_store.delete_document(doc_id)
    repository.delete_document(doc_id)
    return {"deleted": doc_id}
