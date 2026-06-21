import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Optional

from pypdf import PdfReader


@dataclass
class Segment:
    text: str
    page: Optional[int]
    section: Optional[str]


class UnsupportedFileError(ValueError):
    pass


class EmptyDocumentError(ValueError):
    pass


def parse_document(raw: bytes, filename: str) -> list[Segment]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        segments = _parse_pdf(raw)
    elif suffix in {".txt", ".md", ".markdown"}:
        segments = _parse_text(raw.decode("utf-8", errors="replace"))
    else:
        raise UnsupportedFileError(f"Unsupported file type: {suffix or 'unknown'}")

    segments = [s for s in segments if s.text.strip()]
    if not segments:
        raise EmptyDocumentError("No extractable text found in document")
    return segments


def _parse_pdf(raw: bytes) -> list[Segment]:
    reader = PdfReader(BytesIO(raw))
    segments: list[Segment] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        segments.append(Segment(text=_normalize(text), page=index, section=None))
    return segments


def _parse_text(content: str) -> list[Segment]:
    lines = content.splitlines()
    segments: list[Segment] = []
    current_heading: Optional[str] = None
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            segments.append(
                Segment(text=_normalize("\n".join(buffer)), page=None, section=current_heading)
            )
            buffer.clear()

    for line in lines:
        heading = _markdown_heading(line)
        if heading is not None:
            flush()
            current_heading = heading
        else:
            buffer.append(line)
    flush()
    return segments


def _markdown_heading(line: str) -> Optional[str]:
    match = re.match(r"^(#{1,6})\s+(.*\S)\s*$", line)
    return match.group(2).strip() if match else None


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
