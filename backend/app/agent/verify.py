import json
from dataclasses import asdict, dataclass, field
from typing import Optional

from app.agent.tools import format_location
from app.llm.llm_client import chat_json

VERIFY_SYSTEM = """You are a strict grounding verifier for a document Q&A assistant.
You receive a question, a draft answer, and numbered source passages.
Decide, for each factual claim in the draft, whether the passages directly support it.

Return ONLY a JSON object with this shape:
{
  "claims": [
    {"claim": "<short claim text>", "status": "supported|unsupported|conflict", "citations": [<passage numbers>], "note": "<short reason>"}
  ],
  "conflicts": ["<Document A says X, but Document B says Y>"],
  "verified_answer": "<answer rewritten to keep only supported claims, with [n] citations, explicitly stating any conflict; if nothing is supported, say you don't know based on the uploaded documents>",
  "grounded": true
}

Rules:
- A claim is "supported" only if a passage clearly states it; cite those passage numbers.
- Mark "conflict" when passages disagree; include both passage numbers and add a conflicts entry.
- Mark "unsupported" when no passage backs it; do not keep unsupported claims in verified_answer.
- verified_answer must be natural for speech: short sentences, no markdown.
- Output JSON only, no prose around it."""


@dataclass
class ClaimCheck:
    claim: str
    status: str
    citations: list[int]
    note: str = ""


@dataclass
class Verification:
    verified_answer: str
    verdict: str
    grounded: bool
    claims: list[ClaimCheck] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        return data


def verify_answer(question: str, draft: str, passages: list[dict]) -> Verification:
    if not draft.strip():
        return Verification(
            verified_answer="I don't know based on the uploaded documents.",
            verdict="refused",
            grounded=False,
        )
    if not passages:
        return Verification(verified_answer=draft, verdict="unverified", grounded=False)

    rendered = _render_passages(passages)
    user = (
        f"Question:\n{question}\n\nDraft answer:\n{draft}\n\nSource passages:\n{rendered}"
    )
    try:
        raw = chat_json([
            {"role": "system", "content": VERIFY_SYSTEM},
            {"role": "user", "content": user},
        ])
        data = json.loads(raw)
    except Exception:
        return Verification(verified_answer=draft, verdict="unverified", grounded=False)

    claims = [
        ClaimCheck(
            claim=str(c.get("claim", "")).strip(),
            status=str(c.get("status", "unsupported")).strip().lower(),
            citations=[int(n) for n in c.get("citations", []) if isinstance(n, (int, float))],
            note=str(c.get("note", "")).strip(),
        )
        for c in data.get("claims", [])
        if isinstance(c, dict)
    ]
    conflicts = [str(x).strip() for x in data.get("conflicts", []) if str(x).strip()]
    verified_answer = str(data.get("verified_answer", draft)).strip() or draft
    grounded = bool(data.get("grounded", False))
    verdict = _derive_verdict(claims, conflicts, verified_answer)
    if verdict in {"unsupported", "refused"}:
        grounded = False
    return Verification(
        verified_answer=verified_answer,
        verdict=verdict,
        grounded=grounded,
        claims=claims,
        conflicts=conflicts,
    )


def _derive_verdict(claims: list[ClaimCheck], conflicts: list[str], verified_answer: str) -> str:
    statuses = {c.status for c in claims}
    has_real_support = any(c.status == "supported" and c.citations for c in claims)
    if _leads_with_refusal(verified_answer):
        return "refused"
    if _looks_like_refusal(verified_answer) and not has_real_support:
        return "refused"
    if conflicts or "conflict" in statuses:
        return "conflict"
    if not claims:
        return "unverified"
    if statuses == {"supported"}:
        return "grounded"
    if "supported" in statuses:
        return "partially_grounded"
    return "unsupported"


_REFUSAL_PHRASES = (
    "don't know",
    "do not know",
    "not in the",
    "no information",
    "not covered",
    "not mention",
    "doesn't mention",
    "do not mention",
    "don't mention",
    "not specify",
    "doesn't specify",
    "do not contain",
    "don't contain",
    "doesn't contain",
    "cannot find",
    "can't find",
    "not found in",
    "isn't mentioned",
    "is not mentioned",
    "are not mentioned",
)


def _looks_like_refusal(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in _REFUSAL_PHRASES)


def _leads_with_refusal(text: str) -> bool:
    head = text.strip().lower()[:90]
    return any(phrase in head for phrase in _REFUSAL_PHRASES)


def _render_passages(passages: list[dict]) -> str:
    lines = []
    for p in passages:
        n = p.get("n", "?")
        location = format_location(p)
        lines.append(f"[{n}] ({p['filename']}{location})\n{p['text']}")
    return "\n\n".join(lines)
