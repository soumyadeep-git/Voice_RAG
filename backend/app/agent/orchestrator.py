import json
import re
from dataclasses import dataclass, field
from typing import Optional

from groq import BadRequestError

from app.agent.prompts import ANSWER_SYSTEM, REWRITE_SYSTEM
from app.agent.tools import SEARCH_TOOL, CitationRegistry
from app.config import get_settings
from app.llm.groq_client import LLMUnavailableError, chat, complete_text
from app.retrieval.service import retrieve

MAX_TOOL_ITERS = 3
HISTORY_TURNS = 6


@dataclass
class AgentResult:
    answer: str
    rewritten_query: str
    passages: list[dict]
    citations: list[dict]
    tool_calls: list[dict] = field(default_factory=list)


def rewrite_query(question: str, history: Optional[list[dict]] = None) -> str:
    history = history or []
    if not history:
        return question.strip()
    context = "\n".join(f"{t['role']}: {t['content']}" for t in history[-HISTORY_TURNS:])
    user = f"Conversation so far:\n{context}\n\nLatest question: {question}\n\nStandalone search query:"
    settings = get_settings()
    try:
        rewritten = complete_text(REWRITE_SYSTEM, user, model=settings.groq_fast_model)
    except Exception:
        return question.strip()
    return rewritten.splitlines()[0].strip() if rewritten else question.strip()


def answer_question(question: str, history: Optional[list[dict]] = None) -> AgentResult:
    history = history or []
    rewritten = rewrite_query(question, history)
    registry = CitationRegistry()
    tool_log: list[dict] = []

    messages: list[dict] = [{"role": "system", "content": ANSWER_SYSTEM}]
    for turn in history[-HISTORY_TURNS:]:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append(
        {"role": "user", "content": f"{question}\n\n(suggested search query: {rewritten})"}
    )

    try:
        final_text = _agentic_loop(messages, registry, tool_log, rewritten)
    except (BadRequestError, json.JSONDecodeError):
        final_text = _direct_answer(question, rewritten, history, registry, tool_log)

    all_citations = registry.all()
    used = _used_citations(final_text, all_citations)
    return AgentResult(
        answer=final_text.strip(),
        rewritten_query=rewritten,
        passages=all_citations,
        citations=used,
        tool_calls=tool_log,
    )


def _agentic_loop(
    messages: list[dict], registry: CitationRegistry, tool_log: list[dict], rewritten: str
) -> str:
    for _ in range(MAX_TOOL_ITERS):
        response = chat(messages, tools=[SEARCH_TOOL], tool_choice="auto", temperature=0.2)
        message = response.choices[0].message

        if not message.tool_calls:
            return message.content or ""

        messages.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in message.tool_calls
                ],
            }
        )
        for tc in message.tool_calls:
            query = _parse_query(tc.function.arguments) or rewritten
            passages = retrieve(query)
            tool_log.append({"query": query, "results": len(passages)})
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": registry.render(passages)}
            )
    return _force_answer(messages)


def _direct_answer(
    question: str,
    rewritten: str,
    history: list[dict],
    registry: CitationRegistry,
    tool_log: list[dict],
) -> str:
    passages = retrieve(rewritten)
    tool_log.append({"query": rewritten, "results": len(passages), "mode": "direct"})
    rendered = registry.render(passages)
    messages: list[dict] = [{"role": "system", "content": ANSWER_SYSTEM}]
    for turn in history[-HISTORY_TURNS:]:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append(
        {
            "role": "user",
            "content": f"Question: {question}\n\nRetrieved passages:\n{rendered}\n\n"
            "Answer using only these passages with [n] citations. If they do not contain "
            "the answer, say you don't know based on the uploaded documents.",
        }
    )
    try:
        response = chat(messages, temperature=0.2)
        return response.choices[0].message.content or ""
    except LLMUnavailableError:
        raise
    except Exception:
        return "I'm sorry, I couldn't complete that based on the documents."


def _force_answer(messages: list[dict]) -> str:
    messages.append(
        {
            "role": "user",
            "content": "Answer now using only the retrieved passages above, with [n] citations. "
            "If they do not contain the answer, say you don't know.",
        }
    )
    try:
        response = chat(messages, temperature=0.2)
        return response.choices[0].message.content or ""
    except Exception:
        return "I'm sorry, I couldn't complete that based on the documents."


def _parse_query(arguments: str) -> Optional[str]:
    try:
        return json.loads(arguments).get("query")
    except (json.JSONDecodeError, AttributeError):
        return None


def _used_citations(text: str, citations: list[dict]) -> list[dict]:
    nums = {int(n) for n in re.findall(r"\[(\d+)\]", text)}
    return [c for c in citations if c["n"] in nums]
