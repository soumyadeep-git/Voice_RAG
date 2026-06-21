from typing import Optional

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: str
    filename: str
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    num_chunks: int = 0
    status: str
    error: Optional[str] = None
    created_at: Optional[str] = None


class UploadResult(BaseModel):
    accepted: list[DocumentOut]
    rejected: list[dict]
