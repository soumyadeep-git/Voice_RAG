from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent import memory
from app.agent.orchestrator import answer_question
from app.llm.groq_client import LLMUnavailableError

router = APIRouter(prefix="/ask", tags=["ask"])


class Turn(BaseModel):
    role: str
    content: str


class AskRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    history: Optional[list[Turn]] = None


@router.post("")
def ask(req: AskRequest) -> dict:
    conv_id = memory.ensure_conversation(req.conversation_id)
    context = memory.load_context(conv_id)
    history = context["history"] or [t.model_dump() for t in (req.history or [])]
    summary = context["summary"]

    try:
        result = answer_question(req.question, history=history, summary=summary)
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    memory.record_turn(conv_id, req.question, result.answer, result.citations)

    return {
        "conversation_id": conv_id,
        "answer": result.answer,
        "draft_answer": result.draft_answer,
        "rewritten_query": result.rewritten_query,
        "verification": result.verification,
        "citations": result.citations,
        "tool_calls": result.tool_calls,
        "passages": result.passages,
    }
