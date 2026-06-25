import json
import uuid
from typing import Optional

from app.config import get_settings
from app.llm.llm_client import complete_text
from app.store import repository

KEEP_LAST = 8

SUMMARY_SYSTEM = """You maintain a running summary of a voice conversation about uploaded documents.
Given the previous summary and new messages, produce a concise updated summary (<= 120 words)
capturing key topics, document names, entities, and anything needed to resolve later references
like "the second one" or "that document". Output only the summary text."""


def ensure_conversation(conv_id: Optional[str]) -> str:
    conv_id = conv_id or uuid.uuid4().hex
    repository.create_conversation(conv_id)
    return conv_id


def load_context(conv_id: str) -> dict:
    conv = repository.get_conversation(conv_id)
    summary = conv.get("summary") if conv else ""
    recent = repository.get_messages(conv_id)[-KEEP_LAST:]
    history = [{"role": m["role"], "content": m["content"]} for m in recent]
    return {"summary": summary or "", "history": history}


def record_turn(
    conv_id: str, question: str, answer: str, citations: Optional[list] = None
) -> None:
    repository.add_message(uuid.uuid4().hex, conv_id, "user", question)
    repository.add_message(
        uuid.uuid4().hex, conv_id, "assistant", answer, json.dumps(citations or [])
    )
    _maybe_summarize(conv_id)


def _maybe_summarize(conv_id: str) -> None:
    conv = repository.get_conversation(conv_id)
    if not conv:
        return
    summary = conv.get("summary") or ""
    summary_count = conv.get("summary_count") or 0
    total = repository.count_messages(conv_id)
    overflow = total - summary_count - KEEP_LAST
    if overflow <= 0:
        return

    to_fold = repository.get_messages(conv_id, limit=overflow, offset=summary_count)
    folded = "\n".join(f"{m['role']}: {m['content']}" for m in to_fold)
    user = f"Previous summary:\n{summary or '(none)'}\n\nNew messages:\n{folded}\n\nUpdated summary:"
    try:
        new_summary = complete_text(
            SUMMARY_SYSTEM, user, model=get_settings().fast_model, max_tokens=220
        )
    except Exception:
        new_summary = summary
    repository.update_summary(conv_id, new_summary or summary, summary_count + len(to_fold))
