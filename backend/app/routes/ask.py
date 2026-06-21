from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent.orchestrator import answer_question
from app.llm.groq_client import LLMUnavailableError

router = APIRouter(prefix="/ask", tags=["ask"])


class Turn(BaseModel):
    role: str
    content: str


class AskRequest(BaseModel):
    question: str
    history: Optional[list[Turn]] = None


@router.post("")
def ask(req: AskRequest) -> dict:
    history = [t.model_dump() for t in (req.history or [])]
    try:
        result = answer_question(req.question, history)
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {
        "answer": result.answer,
        "rewritten_query": result.rewritten_query,
        "citations": result.citations,
        "tool_calls": result.tool_calls,
        "passages": result.passages,
    }
