import json

from fastapi import APIRouter, HTTPException

from app.agent import memory
from app.store import repository

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("")
def create_conversation() -> dict:
    conv_id = memory.ensure_conversation(None)
    return {"conversation_id": conv_id}


@router.get("")
def list_conversations() -> list[dict]:
    return repository.list_conversations()


@router.get("/{conv_id}/messages")
def get_messages(conv_id: str) -> dict:
    conv = repository.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = repository.get_messages(conv_id)
    for m in messages:
        m["citations"] = json.loads(m["citations"]) if m.get("citations") else []
    return {"conversation_id": conv_id, "summary": conv["summary"], "messages": messages}
