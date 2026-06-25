# Ask My Notes — Voice-Enabled Grounded Document Q&A Agent

Upload a few documents, then talk to them. You ask out loud; the agent rewrites your question in context, retrieves from your sources, verifies every claim against the retrieved passages before it speaks, cites the exact document, surfaces contradictions when two sources disagree, and says "I don't know" when the answer isn't there. You can interrupt it mid-sentence and it stops and listens.

The app opens on a landing page with a playable walkthrough; **Launch** drops you into the voice workspace.

## What I went deep on vs. left shallow

Went deep on: **voice turn-taking** (hybrid STT, VAD endpointing, barge-in, sentence-level streaming TTS), **grounding + verification** (a separate claim-checker that drops unsupported claims and flags conflicts), **agentic answering** (context rewriting + a two-tool loop the model drives), and **retrieval quality** (hybrid dense+sparse with reranking, backed by an eval harness).

Left shallow, on purpose: no speaker/diarization (single user), no auth/multi-user, and plain sentence-aware chunking rather than hierarchical. Conflict detection works but leans on the model's reasoning rather than a dedicated contradiction checker (see Evaluation).

## Requirements coverage

| Requirement | Implementation |
| --- | --- |
| Upload 3–10 docs (PDF/TXT/MD) | `POST /documents`, async parse → chunk → embed → index |
| Real-time streaming voice | WebSocket `/ws`; verified answer streamed sentence-by-sentence and spoken as it arrives |
| Barge-in | Mic activity during playback cancels TTS and sends `interrupt`; backend stops streaming |
| Memory + reference resolution | Last-6 verbatim turns + a rolling LLM summary, persisted in SQLite |
| Agentic answering | Context query-rewrite, then a tool loop the model drives (`search_documents` / `list_documents`) |
| Grounding verification | Second LLM pass checks each claim vs passages and drops unsupported ones (`verify.py`) |
| Conflict handling | Per-claim `conflict` → answer states both sides; UI shows a "Conflicting sources" callout |
| Exact citations | Filename + page/section + char offsets, shown in the source panel |
| Refusal | "I don't know based on the uploaded documents" instead of guessing |
| Evaluation | `backend/eval/run_eval.py`, 4 metrics over a labelled QA set |
| Resilience + persistence | Retry/backoff, graceful audio/parse failures; Chroma + SQLite survive restart |

## How a question is answered

A spoken question is first rewritten into a standalone search query using the rolling summary + recent turns (so "what about the second one?" resolves correctly). The orchestrator then runs a tool loop (`tool_choice=auto`, max 3 iterations): content questions call `search_documents` (hybrid retrieval, registered as `[n]` citations); questions about the corpus itself call `list_documents`. A direct retrieve-then-answer path is the fallback if tool-calling misfires. The draft is then verified before anything is spoken.

## Voice pipeline

STT is hybrid: the browser Web Speech API gives instant interim text (used for barge-in and a "Listening" indicator), while a `MediaRecorder` captures the raw clip from the moment the mic opens and sends it to **Groq Whisper `whisper-large-v3-turbo`** (`POST /transcribe`) for the accurate final transcript the LLM actually receives. A silence timer (1.2s) endpoints the utterance; clips under 400ms are dropped as blips. Whisper gets a spelling-bias `prompt` built from the uploaded corpus (acronyms + frequent capitalised phrases mined from the indexed chunks), so terms like GDPR/CCPA aren't mis-heard.

TTS uses **Cartesia `sonic-2`** (`POST /tts`), synthesised and played per sentence as chunks stream so audio stays in step with the text; the browser voice is the fallback. Speaking while the assistant talks cancels playback, aborts the in-flight TTS request, and interrupts generation over the WebSocket. The mic is push-to-talk (auto-commits on silence, no auto-resume). The backend emits progress stages (`searching → reading → verifying → answering`) and the UI shows a thinking indicator so a multi-second answer never looks frozen.

## Grounding, verification & conflict

`verify_answer` is a separate, adversarial LLM pass kept isolated from drafting. It labels each claim `supported` / `unsupported` / `conflict` with citation numbers, rewrites the answer to keep only supported claims, and refuses if nothing is supported. When two sources give different values for the same fact, the verdict is `conflict` and the answer states both sides ("the 2018 text says 50,000; the amended text says 100,000"). The UI shows just the cited source files plus a conflict flag, rather than a wall of verdict badges.

## Chunking & retrieval

Chunking is sentence-aware with overlap and preserves page/section/char offsets so citations point at a passage, not a whole file. Retrieval is hybrid — dense (Chroma) + sparse (BM25) fused with Reciprocal Rank Fusion — because dense search alone misses exact tokens (numbers like `50,000`, article numbers) while BM25 misses paraphrase. A cross-encoder rerank (`Xenova/ms-marco-MiniLM-L-6-v2`) sharpens the top candidates (20 → 5) and degrades gracefully if it can't load.

## Evaluation

```bash
cd backend
python eval/run_eval.py                     # defaults to the app's model (gpt-oss-120b)
EVAL_IDS=q8,q9 python eval/run_eval.py       # only the conflict questions
EVAL_MODEL=<model> python eval/run_eval.py   # another model on the configured provider
```

The harness ingests `eval/fixtures/` into an isolated store, runs the labelled set in `eval/qa_pairs.yaml` (answerable, multi-source, conflict, unanswerable), and writes `eval/REPORT.md`. Latest run on `gpt-oss-120b`, 11 questions:

| Metric | Result |
| --- | --- |
| Retrieval hit-rate | 89% (8/9) |
| Answer groundedness | 89% (8/9) |
| Refusal accuracy | 100% (2/2) |
| Conflict detection | 50% (1/2) |

Where it fails: **q7** (GDPR fine tiers) is the one retrieval miss — the reranked top-5 didn't surface the exact multi-number passage, so it came back `unverified`. **q9** stated both conflicting values correctly but the verifier labelled it `grounded` instead of `conflict`. So conflict surfacing is the hardest, most verifier-dependent requirement: q8 is flagged correctly, q9 is a near-miss. A dedicated claim-pair contradiction check would make it model-independent.

## Bottlenecks hit along the way

Real problems from building this, not a clean retrospective:

1. **Whisper hallucinated on near-silent clips** — it emitted `"Thank you."` or even Portuguese (`"Então"`) on background noise. Fixed by pinning `language=en` + `temperature=0`, dropping sub-400ms clips, and fixing a bug where `MediaRecorder` chunks were cleared before `onstop` fired (so empty audio was sent and it silently fell back to the worse browser transcript).
2. **STT clipped the first words** — recording started only after speech was detected, so "what are the documents" became "documents". Fixed by recording from the instant the mic opens.
3. **Domain terms mis-heard** (`GDPR → GTPL`, `16 → 60`) — fixed with Whisper as the accurate pass, a corpus-derived vocabulary bias prompt, and cleaner capture (echo cancellation / noise suppression / gain, mono, 128 kbps).
4. **Rate limits during eval** — Groq's free-tier 70B has a ~100k tokens/day cap and one eval run ≈ that budget, so runs kept dying with 429s. Refactored to a provider-agnostic OpenAI-compatible client and moved to Cerebras `gpt-oss-120b`; that tier didn't serve Llama-70B either, so I queried `/models` and standardised on `gpt-oss-120b`. Switching providers is now a 3-line `.env` change.
5. **Robotic TTS** — replaced the browser voice with Cartesia `sonic-2` (browser kept only as fallback).
6. **App looked frozen** — the whole pipeline ran before any output. Fixed by streaming progress stages + a thinking indicator.
7. **Audio lagged the text** — the full answer was synthesised only after rendering. Fixed by synthesising per sentence as chunks stream.
8. **Transcript visibly "autocorrected"** — the live browser guess got overwritten by Whisper, which felt like words being changed. Fixed by dropping the jittery live preview for a stable "Listening" indicator, then showing the accurate transcript once.

## Resilience & persistence

`tenacity` retry/backoff on every LLM call. Empty/short/no-speech audio is dropped rather than transcribed; Whisper and TTS both fall back to the browser. Tool-calling misfires fall back to direct retrieve-then-answer. A global handler returns a clean 500 instead of a stack trace, and the WebSocket reconnects with backoff. Uploaded chunks + embeddings (Chroma) and conversation history (SQLite) persist under `backend/storage/` and survive a restart.

## Prompt design

Three focused prompts: the **rewrite** prompt turns a context-dependent spoken question into one standalone search query; the **answer** prompt constrains the model to the retrieved passages, requires `[n]` citations, and mandates an explicit "I don't know" when unsupported; the **verify** prompt is adversarial — it assumes claims are unsupported until a passage proves them and treats same-fact disagreement as a conflict rather than picking a side.

## Tech stack

- **Backend:** FastAPI + Uvicorn, WebSocket streaming, keys held server-side
- **LLM:** any OpenAI-compatible endpoint via the `openai` SDK — Cerebras `gpt-oss-120b` by default; swap to Groq/OpenRouter/Ollama in `.env`
- **STT:** Groq Whisper `whisper-large-v3-turbo` + browser Web Speech (interim/barge-in)
- **TTS:** Cartesia `sonic-2` (browser fallback)
- **Embeddings / retrieval:** local `fastembed` `bge-small-en-v1.5`, Chroma (dense) + `rank_bm25` (sparse) + RRF + cross-encoder rerank
- **Storage:** Chroma (vectors) + SQLite (chunks, conversations, messages)
- **Frontend:** React 19 + Vite + TypeScript

## Setup

```bash
# backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set LLM_API_KEY (Cerebras), STT_API_KEY (Groq), CARTESIA_API_KEY
uvicorn app.main:app --reload   # http://127.0.0.1:8000

# frontend (new terminal)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

Open `http://localhost:5173/` in Chrome or Edge (Web Speech API). Without the Cartesia/Whisper keys it still runs on the browser's built-in STT/TTS.

## Sample corpus

`backend/eval/fixtures/` holds real public privacy-law text, chosen because the sources overlap *and* conflict: GDPR Articles 7/8/17/33/83 (verbatim), CCPA consumer rights, and the original 2018 CCPA vs the CPRA-amended version — which contradict on the consumer-count threshold (50,000 → 100,000), the deliberate conflict used to test conflict surfacing. The app never pre-loads these; it only answers over what you upload.

## Future work

Model-independent conflict detection (a dedicated claim-pair checker); lower time-to-first-word by streaming the draft token-by-token; hierarchical chunking + metadata filtering for larger corpora; a fully server-side streaming STT for accent/browser consistency.
