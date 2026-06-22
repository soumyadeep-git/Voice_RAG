# Ask My Notes — Voice-Enabled Grounded Document Q&A Agent

Upload a small set of documents and have a **real-time spoken conversation** about them. Every answer is retrieved from your sources, **verified against them**, **cited to the exact passage**, and when two documents disagree the contradiction is **surfaced rather than hidden**. If the answer isn't in the documents, the agent says so instead of guessing.

The app opens on a landing page with a playable walkthrough; **Launch** drops you into the voice workspace.

---

## Requirements coverage

| Requirement | How it's met |
| --- | --- |
| Document upload (PDF / TXT / MD) | Async ingestion: parse → structure-aware chunk → embed → index |
| Real-time spoken conversation | Browser Web Speech (STT/TTS) over a WebSocket; answers stream sentence-by-sentence |
| Interruption (barge-in) | Mic activity cancels TTS instantly and sends an `interrupt` to the backend |
| Remembers context | Bounded multi-turn memory: last-N turns + a rolling LLM summary, stored in SQLite |
| Agentic reasoning | LLM orchestrator rewrites the query in context and calls a `search_documents` tool, multi-query |
| Verifies answers | A second LLM pass checks every claim against retrieved passages before it's spoken |
| Handles conflicting sources | Per-claim verification marks `conflict` and the answer states both sides |
| Cites exact passages | Citations carry filename + page/section + char offsets; shown in the source panel |
| Refuses when unsupported | "I don't know based on the uploaded documents" instead of hallucinating |
| Evaluation harness | Scripted QA set (answerable, multi-source, conflict, unanswerable) with metrics |

---

## Architecture

```
┌─────────────────────────────┐         ┌──────────────────────────────────────┐
│  Frontend (React + Vite)    │         │  Backend (FastAPI)                     │
│                             │         │                                        │
│  Landing + animated demo    │         │  /documents  ingest + manage           │
│  Voice workspace            │  HTTP   │  /search     retrieval (debug)         │
│   - Web Speech STT/TTS      │ ──────► │  /ask        text Q&A                  │
│   - barge-in                │   WS    │  /ws         streaming voice Q&A       │
│   - upload / sources panel  │ ◄─────► │  /conversations  history               │
└─────────────────────────────┘         │                                        │
                                         │  Ingestion → Retrieval → Agent → Verify │
                                         └───────┬───────────────┬───────────────┘
                                                 │               │
                                  ┌──────────────▼──┐   ┌────────▼──────────┐
                                  │ Chroma (vectors) │   │ Groq LLM API      │
                                  │ SQLite (chunks,  │   │ 70B answer/verify │
                                  │  convos, BM25)   │   │ 8B  query rewrite │
                                  │ fastembed (local)│   └───────────────────┘
                                  └──────────────────┘
```

### Pipeline

1. **Ingestion** (`app/ingestion`) — parse PDF/TXT/MD, detect headings, normalize whitespace, then **structure-aware chunking** (sentence-aware, fixed size + overlap) preserving page/section/char offsets. Chunks are embedded with a local `fastembed` model and stored in Chroma + SQLite.
2. **Retrieval** (`app/retrieval`) — **hybrid search**: dense (Chroma vector search) + sparse (BM25 keyword) fused with **Reciprocal Rank Fusion**, then optional **cross-encoder reranking** for precision. Results are LRU-cached and invalidated when documents change.
3. **Agent** (`app/agent/orchestrator.py`) — rewrites the question using conversation context, then calls a `search_documents` tool (with a direct retrieve-then-answer fallback if tool-calling misfires). Drafts an answer grounded in the retrieved passages.
4. **Verification** (`app/agent/verify.py`) — a strict second pass extracts each claim, marks it `supported` / `unsupported` / `conflict` with passage citations, rewrites the answer to keep only supported claims, surfaces conflicts, and refuses if nothing is supported. The verdict (`grounded` / `partially_grounded` / `conflict` / `refused`) drives the UI badge.
5. **Memory** (`app/agent/memory.py`) — keeps the last N turns verbatim and a rolling summary of older turns, bounding context size for long conversations.
6. **Voice** (frontend + `/ws`) — STT/TTS run in the browser for low latency; verified answers stream back over the WebSocket and are spoken sentence-by-sentence. Speaking into the mic cancels playback and interrupts generation.

---

## Tech stack

- **Backend:** FastAPI (Python), keeps the Groq key server-side and streams over WebSocket
- **LLM:** Groq — `llama-3.3-70b-versatile` (answering + verification), `llama-3.1-8b-instant` (query rewrite)
- **Embeddings:** `fastembed` local `BAAI/bge-small-en-v1.5` (warmed on startup)
- **Retrieval:** Chroma (dense) + `rank_bm25` (sparse) + RRF + optional cross-encoder rerank
- **Storage:** Chroma (vectors) + SQLite (chunks, conversations, messages)
- **Voice:** browser Web Speech API (STT/TTS), Groq `whisper-large-v3-turbo` fallback
- **Frontend:** React 19 + Vite + TypeScript, React Router

---

## Setup

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then set GROQ_API_KEY
uvicorn app.main:app --reload # http://127.0.0.1:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173  (proxies API/WS to :8000)
```

Open `http://localhost:5173/` for the landing page, or `/app` for the workspace. Use Chrome or Edge for voice.

> Voice (Web Speech API) is best supported in Chromium browsers. Text input works everywhere.

---

## Sample corpus (real-world data)

The demo/eval corpus in `backend/eval/fixtures/` uses **real public privacy-law text**, chosen because the sources genuinely overlap *and* conflict:

- **GDPR** Articles 7, 8, 17, 33, 83 (verbatim, from gdpr-info.eu)
- **CCPA** consumer rights (from the California Attorney General) + real statutory thresholds/penalties
- **Original 2018 CCPA** vs the **CPRA-amended** version — these genuinely contradict each other on the consumer-count threshold (**50,000 → 100,000**), which is the deliberate conflict used to test conflict surfacing.

The running app never pre-loads these — it only answers over what *you* upload. They exist for a reproducible demo and eval.

---

## Evaluation

```bash
cd backend
python eval/run_eval.py                                  # default: 8B (cheap, free-tier friendly)
EVAL_MODEL=llama-3.3-70b-versatile python eval/run_eval.py  # production model
```

The harness ingests the fixtures into an isolated store, runs a labelled QA set (`eval/qa_pairs.yaml`) covering **answerable, multi-source synthesis, genuine conflict, and unanswerable** questions, and reports retrieval hit-rate, groundedness, refusal accuracy, and conflict detection to `eval/REPORT.md`.

### A finding worth noting

Conflict surfacing is the hardest requirement and it is **model-dependent**:

- On the lighter **8B** model the pipeline is strong on the straightforward cases (retrieval ~89%, groundedness ~89%, **refusal 100%**) but it does **not** reliably surface contradictions — it tends to pick one value or refuse.
- On the production **70B** model the same conflict question (`50,000 vs 100,000`) is correctly returned as `verdict=conflict`.

So the system distinguishes *comparison across sources* (e.g. GDPR opt-in vs CCPA opt-out — synthesized and grounded) from *true contradiction* (same fact, two values — flagged as conflict), and the 70B model is needed for the latter. See `eval/REPORT.md` for the latest run.

> Free-tier note: the 70B model has a ~100k-tokens/day cap, and one full eval ≈ that budget. The eval defaults to 8B for reproducibility; run with `EVAL_MODEL=llama-3.3-70b-versatile` when you have headroom.

---

## Design decisions & trade-offs

- **Browser STT/TTS over server-side audio** — near-zero added latency and instant, cancellable barge-in, at the cost of depending on the Web Speech API (Groq Whisper is the fallback).
- **Stream only *verified* answers** — slightly higher time-to-first-word in exchange for never speaking an ungrounded claim.
- **Hybrid retrieval + RRF + rerank** — dense search alone misses exact terms (numbers, names); BM25 covers that, and reranking sharpens precision before the LLM sees anything.
- **Separate verification pass** — grounding/conflict/refusal logic is isolated from drafting, so it's testable and the verdict is explicit.
- **Local embeddings** — no per-token embedding cost and no extra vendor; warmed on startup so the first query is fast.

## Limitations & future work

- Conflict detection depends on the answering model's reasoning (see above); a dedicated claim-pair contradiction check would make it model-independent.
- Web Speech API quality varies by browser/accent.
- Larger, messier real-world corpora would benefit from hierarchical chunking and metadata filtering.

---

## Project structure

```
backend/
  app/
    ingestion/   parse + chunk + ingest service
    embeddings/  fastembed wrapper
    retrieval/   hybrid search, BM25, rerank, RRF, cache
    agent/       orchestrator, verify, memory, prompts, tools, guards
    routes/      documents, search, ask, conversations, voice_ws
    store/       db, repository, vector_store
    llm/         groq client (retry/backoff)
  eval/          run_eval.py, qa_pairs.yaml, fixtures/, REPORT.md
frontend/
  src/
    pages/       LandingPage
    components/   DemoPlayer, UploadPanel, ConversationView, SourcePanel, VoiceConsole
    lib/         api, speech (STT/TTS), voiceClient (WS)
```

## Branches

- **`main`** — stable v1 (backend + voice workspace + eval).
- **`v2-frontend-revamp`** — landing page, playable demo, and themed workspace; merged into `main` via Pull Request.
