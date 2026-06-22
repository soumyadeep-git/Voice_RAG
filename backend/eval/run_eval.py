import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["CHROMA_DIR"] = "storage/eval_chroma"
os.environ["SQLITE_PATH"] = "storage/eval.sqlite"
os.environ["DATA_DIR"] = "storage/eval_data"

# The eval makes many LLM calls; the free-tier 70B model has a small daily token
# budget, so the harness runs on the lighter "instant" model (much larger cap).
# Production answers still use the 70B model configured in .env.
EVAL_MODEL = os.environ.get("EVAL_MODEL", "llama-3.1-8b-instant")
os.environ["GROQ_ANSWER_MODEL"] = EVAL_MODEL

import yaml  # noqa: E402

from app.config import get_settings  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parents[1]
SAMPLE_DIR = EVAL_DIR / "fixtures"
REPORT_PATH = EVAL_DIR / "REPORT.md"
PAUSE_SECONDS = 2.0


def reset_store() -> None:
    settings = get_settings()
    shutil.rmtree(settings.chroma_path, ignore_errors=True)
    settings.chroma_path.mkdir(parents=True, exist_ok=True)
    if settings.sqlite_file.exists():
        settings.sqlite_file.unlink()


def ingest_samples() -> int:
    from app.ingestion.service import ingest_document, new_document_id
    from app.store import repository
    from app.store.db import init_db

    init_db()
    count = 0
    for path in sorted(SAMPLE_DIR.glob("*.md")):
        raw = path.read_bytes()
        doc_id = new_document_id()
        repository.create_document(doc_id, path.name, "text/markdown", len(raw))
        ingest_document(doc_id, raw, path.name)
        count += 1
    return count


def run() -> None:
    reset_store()
    n_docs = ingest_samples()
    print(f"Ingested {n_docs} documents from {SAMPLE_DIR.name}/\n")

    from app.agent.orchestrator import answer_question
    from app.retrieval.service import retrieve

    qa = yaml.safe_load((EVAL_DIR / "qa_pairs.yaml").read_text())

    rows = []
    retrieval_total = retrieval_hits = 0
    grounded_total = grounded_ok = 0
    refusal_total = refusal_ok = 0
    conflict_total = conflict_ok = 0

    for item in qa:
        question = item["question"]
        qtype = item["type"]
        expect_sources = set(item.get("expect_sources", []))
        expect_keywords = [k.lower() for k in item.get("expect_keywords", [])]

        passages = retrieve(question)
        retrieved_files = {p["filename"] for p in passages}
        result = answer_question(question)
        verdict = result.verification["verdict"]
        answer = result.answer
        answer_l = answer.lower()

        retrieval_hit = None
        if qtype in {"answerable", "conflict"}:
            retrieval_total += 1
            retrieval_hit = expect_sources.issubset(retrieved_files)
            retrieval_hits += int(retrieval_hit)

            grounded_total += 1
            grounded = verdict in {"grounded", "partially_grounded", "conflict"} and bool(
                result.citations
            )
            grounded_ok += int(grounded)

            kw_hit = any(k in answer_l for k in expect_keywords) if expect_keywords else True
        else:
            kw_hit = True

        if qtype == "conflict":
            conflict_total += 1
            conflict_ok += int(verdict == "conflict")

        if qtype == "unanswerable":
            refusal_total += 1
            refusal_ok += int(verdict == "refused")

        rows.append(
            {
                "id": item["id"],
                "type": qtype,
                "verdict": verdict,
                "retrieval_hit": retrieval_hit,
                "kw_hit": kw_hit,
                "answer": answer,
            }
        )
        print(
            f"[{item['id']}] {qtype:12} verdict={verdict:18} "
            f"retrieval={'-' if retrieval_hit is None else ('hit' if retrieval_hit else 'MISS')} "
            f"kw={'ok' if kw_hit else 'MISS'}"
        )
        time.sleep(PAUSE_SECONDS)

    report = _format_report(
        rows,
        retrieval_hits,
        retrieval_total,
        grounded_ok,
        grounded_total,
        refusal_ok,
        refusal_total,
        conflict_ok,
        conflict_total,
    )
    print("\n" + report)
    REPORT_PATH.write_text(report)
    print(f"\nReport written to {REPORT_PATH.relative_to(REPO_ROOT)}")


def _pct(num: int, den: int) -> str:
    return f"{(100 * num / den):.0f}% ({num}/{den})" if den else "n/a"


def _format_report(
    rows,
    r_hits,
    r_total,
    g_ok,
    g_total,
    ref_ok,
    ref_total,
    c_ok,
    c_total,
) -> str:
    lines = ["# Evaluation Report", "", f"Pipeline model: `{EVAL_MODEL}` · corpus: `backend/eval/fixtures/`", "", "## Metrics", ""]
    lines.append(f"- Retrieval hit-rate: {_pct(r_hits, r_total)}")
    lines.append(f"- Answer groundedness: {_pct(g_ok, g_total)}")
    lines.append(f"- Refusal accuracy: {_pct(ref_ok, ref_total)}")
    lines.append(f"- Conflict detection: {_pct(c_ok, c_total)}")
    lines.append("")
    lines.append("## Per-question results")
    lines.append("")
    lines.append("| id | type | verdict | retrieval | keywords |")
    lines.append("| --- | --- | --- | --- | --- |")
    for r in rows:
        ret = "-" if r["retrieval_hit"] is None else ("hit" if r["retrieval_hit"] else "MISS")
        lines.append(
            f"| {r['id']} | {r['type']} | {r['verdict']} | {ret} | "
            f"{'ok' if r['kw_hit'] else 'MISS'} |"
        )
    failures = [
        r
        for r in rows
        if r["retrieval_hit"] is False
        or not r["kw_hit"]
        or (r["type"] == "unanswerable" and r["verdict"] != "refused")
        or (r["type"] == "conflict" and r["verdict"] != "conflict")
    ]
    lines.append("")
    lines.append("## Failures / weaknesses")
    lines.append("")
    if not failures:
        lines.append("No failures in this run.")
    else:
        for r in failures:
            lines.append(f"- [{r['id']}] {r['type']}: verdict={r['verdict']} — {r['answer'][:120]}")
    return "\n".join(lines)


if __name__ == "__main__":
    run()
