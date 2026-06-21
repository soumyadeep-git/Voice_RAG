import re

from app.store import repository

NO_SPEECH_MESSAGE = "I didn't catch that. Could you say it again?"
NO_DOCUMENTS_MESSAGE = "No documents are ready yet. Please upload a few files first."


def is_meaningful(question: str) -> bool:
    return len(re.sub(r"[^a-zA-Z0-9]", "", question or "")) >= 2


def has_documents() -> bool:
    return repository.count_ready_documents() > 0
