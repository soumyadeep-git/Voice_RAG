import re
from dataclasses import dataclass
from typing import Optional

from app.ingestion.parse import Segment

TARGET_CHARS = 900
OVERLAP_CHARS = 150
MIN_CHARS = 60


@dataclass
class Chunk:
    text: str
    page: Optional[int]
    section: Optional[str]
    char_start: int
    char_end: int


def chunk_segments(segments: list[Segment]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for segment in segments:
        chunks.extend(_chunk_one(segment))
    return _merge_tiny(chunks)


def _chunk_one(segment: Segment) -> list[Chunk]:
    text = segment.text
    if len(text) <= TARGET_CHARS:
        return [Chunk(text, segment.page, segment.section, 0, len(text))]

    spans = _sentence_spans(text)
    chunks: list[Chunk] = []
    start = 0
    cursor = 0
    while cursor < len(spans):
        end = cursor
        while end < len(spans) and spans[end][1] - start < TARGET_CHARS:
            end += 1
        end = max(end, cursor + 1)
        char_start = spans[cursor][0]
        char_end = spans[end - 1][1]
        chunks.append(
            Chunk(text[char_start:char_end].strip(), segment.page, segment.section, char_start, char_end)
        )
        if end >= len(spans):
            break
        start = max(char_end - OVERLAP_CHARS, 0)
        cursor = _span_at(spans, start, end)
    return chunks


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    for match in re.finditer(r"[^\n.!?]+[.!?]?(?:\s+|\n+|$)", text):
        end = match.end()
        if end > start:
            spans.append((start, end))
            start = end
    if start < len(text):
        spans.append((start, len(text)))
    return spans or [(0, len(text))]


def _span_at(spans: list[tuple[int, int]], char_pos: int, fallback_index: int) -> int:
    for i, (s, _e) in enumerate(spans):
        if s >= char_pos:
            return i
    return fallback_index


def _merge_tiny(chunks: list[Chunk]) -> list[Chunk]:
    merged: list[Chunk] = []
    for chunk in chunks:
        if (
            merged
            and len(chunk.text) < MIN_CHARS
            and merged[-1].page == chunk.page
            and merged[-1].section == chunk.section
        ):
            prev = merged[-1]
            merged[-1] = Chunk(
                (prev.text + " " + chunk.text).strip(),
                prev.page,
                prev.section,
                prev.char_start,
                chunk.char_end,
            )
        elif chunk.text:
            merged.append(chunk)
    return merged
