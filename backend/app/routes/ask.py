from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent import guards, memory
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

    if not guards.is_meaningful(req.question):
        return _simple_reply(conv_id, guards.NO_SPEECH_MESSAGE, "no_speech")
    if not guards.has_documents():
        return _simple_reply(conv_id, guards.NO_DOCUMENTS_MESSAGE, "no_documents")

    context = memory.load_context(conv_id)
    history = context["history"] or [t.model_dump() for t in (req.history or [])]
    summary = context["summary"]

    try:
        result = answer_question(req.question, history=history, summary=summary)
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to process the question")

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


def _simple_reply(conv_id: str, message: str, verdict: str) -> dict:
    return {
        "conversation_id": conv_id,
        "answer": message,
        "draft_answer": message,
        "rewritten_query": "",
        "verification": {
            "verified_answer": message,
            "verdict": verdict,
            "grounded": False,
            "claims": [],
            "conflicts": [],
        },
        "citations": [],
        "tool_calls": [],
        "passages": [],
    }
