# Ask My Notes — Voice-Enabled Grounded Document Q&A Agent

Upload a small set of documents, then **talk to them**. You ask out loud, the agent
reasons about how to answer, retrieves from your sources, **verifies every claim against
the retrieved passages before it speaks**, cites the exact document, surfaces
contradictions when two sources disagree, and says *"I don't know"* when the answer
isn't there. You can **interrupt it mid-sentence** and it stops and listens.

The app opens on a landing page with a playable walkthrough; **Launch** drops you into
the voice workspace.

---

## What I went deep on vs. left shallow

The spec is deliberately larger than the time allows, so I prioritised:

**Went deep:**
- **Voice turn-taking** — hybrid STT (browser interim + Whisper final), VAD endpointing,
  barge-in, sentence-level streaming TTS, and a lot of work on *perceived* latency.
- **Grounding + verification** — a separate claim-checking pass that rewrites the answer
  to drop unsupported claims and explicitly flags `conflict` when sources disagree.
- **Agentic answering** — context-aware query rewriting plus a real two-tool loop the
  model chooses between (`search_documents` vs `list_documents`).
- **Retrieval quality** — hybrid dense+sparse with RRF and cross-encoder reranking,
  proven with a labelled eval harness.

**Left shallow (conscious trade-offs):**
- **Speaker/turn detection** — single-user assumption; no diarization.
- **Auth / multi-user** — single local store, no accounts.
- **Chunking** — solid sentence-aware fixed-window chunking, not hierarchical/semantic.
- **Conflict detection is model-dependent** (see *Evaluation* and *Bottlenecks*) — it
  works on a capable model but I did not build a model-independent contradiction checker.

---

## Requirements coverage

| Requirement | Implementation |
| --- | --- |
| Upload 3–10 docs (PDF/TXT/MD) | `POST /documents`, async parse → chunk → embed → index (`app/ingestion`) |
| Real-time streaming voice | WebSocket `/ws`; verified answer streamed **sentence-by-sentence** and spoken as it arrives |
| Barge-in / interruption | Mic activity during playback cancels TTS instantly + sends `interrupt`; backend stops streaming |
| Multi-turn memory + reference resolution | Last-N verbatim turns + rolling LLM summary, persisted in SQLite (`app/agent/memory.py`) |
| Agentic answering | Query rewrite in context, then a tool loop the model drives (`app/agent/orchestrator.py`) |
| Grounding verification | Second LLM pass checks each claim vs retrieved passages, drops unsupported ones (`app/agent/verify.py`) |
| Conflict handling | Per-claim `conflict` status → answer states both sides; UI shows a "Conflicting sources" callout |
| Exact citations | Citations carry filename + page/section + char offsets, shown in the source panel |
| Refusal | "I don't know based on the uploaded documents" instead of guessing |
| Evaluation harness | `backend/eval/run_eval.py`: answerable / multi-source / conflict / unanswerable, 4 metrics |
| Resilience + persistence | Retry/backoff, graceful audio/parse/timeout handling; Chroma + SQLite survive restart |

---

## Architecture

```
┌──────────────────────────────┐                 ┌─────────────────────────────────────────────┐
│  Frontend (React + Vite + TS) │                 │  Backend (FastAPI)                            │
│                              │   POST /documents │  ingestion:  parse → chunk → embed → index    │
│  • Landing + demo player     │ ───────────────► │  POST /transcribe   Whisper STT               │
│  • Voice workspace           │   POST /transcribe │  POST /tts          Cartesia TTS             │
│     - Web Speech (interim)   │   POST /tts        │  GET  /search       retrieval (debug)         │
│     - MediaRecorder capture  │ ◄──────────────► │  WS   /ws           streaming voice Q&A        │
│     - barge-in + VAD         │   WS  /ws          │  GET  /conversations  history                │
│  • Upload / sources panels   │                   │                                               │
└──────────────────────────────┘                 │   Retrieval → Agent (rewrite+tools) → Verify  │
                                                   └───────┬───────────────────────┬───────────────┘
                                          ┌────────────────▼───────┐     ┌─────────▼─────────────────┐
                                          │ Chroma  (dense vectors) │     │ LLM: OpenAI-compatible    │
                                          │ SQLite  (chunks, convos,│     │ endpoint (Cerebras default)│
                                          │          messages)      │     │ Whisper STT (Groq)         │
                                          │ fastembed bge-small     │     │ Cartesia sonic-2 TTS       │
                                          │ rank_bm25 (sparse)      │     └────────────────────────────┘
                                          └─────────────────────────┘
```

### End-to-end data flow

1. **Ingestion** (`app/ingestion`) — parse PDF (`pypdf`) / TXT / MD, detect headings,
   normalise whitespace, then **structure-aware chunking**: sentence-aware, fixed window
   with overlap, keeping `page` / `section` / char offsets so a *passage* (not a whole
   doc) can be cited. Chunks are embedded locally with `fastembed` and written to Chroma
   (vectors) + SQLite (text + metadata). Ingestion runs in a background thread so the
   upload request returns immediately and the UI polls status.
2. **Retrieval** (`app/retrieval`) — **hybrid**: dense (Chroma) + sparse (BM25) fused with
   **Reciprocal Rank Fusion**, then a **cross-encoder rerank** (`fastembed` TextCrossEncoder)
   for precision. Candidates=20 → top_k=5. Results are LRU-cached and invalidated when the
   corpus changes.
3. **Agent** (`app/agent/orchestrator.py`) — rewrites the spoken question into a standalone
   search query using conversation context, then runs a **tool loop** (below). Falls back
   to a direct retrieve-then-answer path if tool-calling misfires.
4. **Verification** (`app/agent/verify.py`) — a strict second pass extracts each claim,
   marks it `supported` / `unsupported` / `conflict` with citation numbers, rewrites the
   spoken answer to keep only supported claims, surfaces conflicts, and refuses if nothing
   is supported. The verdict drives the UI.
5. **Memory** (`app/agent/memory.py`) — last `HISTORY_TURNS` (6) turns verbatim + a rolling
   LLM summary of older turns, so context stays bounded over a long conversation.
6. **Voice** (frontend + `/ws`) — the verified answer streams back over the WebSocket and
   is synthesised + spoken sentence-by-sentence; speaking into the mic cancels playback and
   interrupts generation.

---

## Voice pipeline (deep dive)

This is the part I spent the most time on, because "STT → LLM → TTS" is easy but *natural
turn-taking* is not.

**STT — hybrid, browser + Whisper.** The browser Web Speech API gives **instant interim
text** (used purely for barge-in detection and a "Listening" indicator). In parallel, a
`MediaRecorder` captures the raw audio from the moment the mic opens. On endpoint, the
recorded clip is sent to **Groq Whisper `whisper-large-v3-turbo`** (`POST /transcribe`) for
an accurate final transcript, which is what the LLM actually receives. Browser STT alone
mangled domain terms (`GDPR → "GTPL"`, `16 → "60"`); Whisper fixes those.

**Smart endpointing (VAD).** A silence timer (`ENDPOINT_SILENCE_MS = 1200`) commits the
utterance after the speaker pauses, rather than on a fixed button release. Clips shorter
than `MIN_UTTERANCE_MS = 400` are discarded as blips/echo.

**Domain-biased transcription.** Whisper is given a `prompt` built **from the uploaded
corpus** (`app/llm/stt.py:build_vocab_prompt`) — it mines acronyms (`GDPR`, `CCPA`, `CPRA`)
and frequent capitalised phrases from the indexed chunks and feeds them as a spelling bias.
This auto-adapts to whatever you upload; no hardcoded vocabulary.

**TTS — Cartesia.** Final answers are spoken with **Cartesia `sonic-2`** (`POST /tts`) for a
natural voice, with the browser `speechSynthesis` as a graceful fallback if the key is
absent or the call fails. Audio is synthesised and played **per sentence** as chunks stream,
so speech starts ~one short sentence's latency after the text appears instead of waiting for
the whole answer.

**Barge-in.** While the assistant is speaking, any real speech from the user immediately
(a) cancels the current audio + aborts the in-flight TTS request, and (b) sends an
`interrupt` over the WebSocket so the backend stops streaming the rest of the answer.

**Turn model.** Push-to-talk: the mic opens on tap, auto-commits on silence, and does **not**
auto-resume after the assistant speaks — the user taps again to talk. This was a direct
response to "it's still listening after I stopped talking".

**Progress feedback.** The backend emits granular stages over the WS
(`rewriting → searching → reading → verifying → answering`) and the UI shows an animated
"thinking" bubble, so a multi-second answer never looks like a crash.

---

## Agent design

```
spoken question
   │
   ├─ rewrite_query()         fast model, uses summary + last-N turns → standalone search query
   │
   ├─ _agentic_loop()         up to MAX_TOOL_ITERS=3, tool_choice="auto", tools:
   │     • search_documents(query)   → hybrid retrieve, registered as citations [n]
   │     • list_documents()          → corpus/metadata questions ("what files do I have?")
   │   (fallbacks: _direct_answer on tool misfire, _force_answer after max iters)
   │
   └─ verify_answer()         claim-by-claim grounding/conflict/refusal → spoken answer
```

- **Query rewriting** resolves references ("what about the second one?") using the rolling
  summary + recent turns before retrieval, so follow-ups hit the right passages.
- **Two real tools**, and the model *chooses*: content questions go to `search_documents`;
  questions about the document set itself go to `list_documents` (answered from the registry,
  not passage content — these get an `info` verdict and skip the grounding check, since
  there's nothing to ground against).
- **Memory** is bounded on purpose: verbatim recent turns for precise reference resolution +
  a summary for older context, so token usage doesn't grow unbounded.

---

## Grounding, verification & conflict handling

`verify_answer` (`app/agent/verify.py`) is a separate LLM pass — kept isolated from drafting
so it's testable and the verdict is explicit:

- Extracts each **claim** and labels it `supported` / `unsupported` / `conflict`, each with
  the citation numbers that back it.
- **Rewrites** the answer to keep only supported claims; unsupported ones are dropped rather
  than spoken.
- **Conflict**: when two sources give different values for the same fact, the verdict is
  `conflict` and the answer states both sides ("the 2018 text says 50,000; the amended text
  says 100,000"). The UI shows a "Conflicting sources" callout.
- **Refusal**: if nothing supports the answer, it refuses by voice and on screen. Refusal
  phrasing is detected robustly so a hedged "I don't know…" isn't mislabelled as grounded.

The UI deliberately shows just the **cited source files** + a conflict flag, rather than a
wall of verdict badges (a UX iteration after the badges felt noisy).

---

## Chunking & retrieval strategy

- **Chunking** preserves structure (page/section/offsets) so citations point at a passage.
  Sentence-aware splitting avoids cutting mid-sentence; overlap preserves context across
  boundaries.
- **Hybrid retrieval** because dense search alone misses exact tokens (numbers like
  `50,000`, names, article numbers); BM25 covers lexical matches, dense covers paraphrase,
  and **RRF** fuses them without tuning score scales.
- **Cross-encoder rerank** (`Xenova/ms-marco-MiniLM-L-6-v2`) sharpens precision on the top
  candidates before the LLM sees anything. It degrades gracefully: if the reranker can't
  load, retrieval still returns the fused list.

---

## Evaluation

```bash
cd backend
python eval/run_eval.py                                   # defaults to the app's model (gpt-oss-120b)
EVAL_IDS=q8,q9 python eval/run_eval.py                    # run only the conflict questions
EVAL_MODEL=<model> python eval/run_eval.py                # try another model on the configured provider
```

The harness ingests `eval/fixtures/` into an **isolated** store, runs the labelled set in
`eval/qa_pairs.yaml` (answerable, multi-source synthesis, genuine conflict, unanswerable),
and writes `eval/REPORT.md` with four metrics. Latest run on the shipped model
(`gpt-oss-120b`), 11 questions:

| Metric | Result |
| --- | --- |
| Retrieval hit-rate | **89%** (8/9) |
| Answer groundedness | **89%** (8/9) |
| Refusal accuracy | **100%** (2/2) |
| Conflict detection | **50%** (1/2) |

**Where it fails (honestly):**
- **q7** (GDPR fine tiers) — the only retrieval miss; the reranked top-5 didn't surface the
  exact fine passage, so the answer came back `unverified`. Lexical/dense fusion isn't enough
  for this multi-number passage.
- **q9** (CCPA threshold conflict) — the answer *did* state both values ("the original set
  50,000… the later version raised it to 100,000") but the verifier labelled it `grounded`
  rather than `conflict`. So conflict surfacing is the hardest requirement and is
  **model/verifier-dependent**: q8 is flagged correctly, q9 is a near-miss. A dedicated
  claim-pair contradiction check (rather than relying on the verifier's judgement) would make
  this model-independent — see *Future work*.

---

## Bottlenecks hit along the way (and the fixes)

Real problems from building this, not a clean retrospective:

1. **Whisper hallucinated on near-silent clips** — it would emit `"Thank you."` or even
   Portuguese (`"Então"`) on background noise. Fixes: pin `language="en"` + `temperature=0.0`,
   and a `MIN_UTTERANCE_MS` guard to drop sub-400 ms clips. There was also a nasty bug where
   `MediaRecorder` chunks were cleared *before* `onstop` fired, so empty audio was sent to
   Whisper and it silently fell back to the worse browser transcript.

2. **STT clipped the first words** — `MediaRecorder` was started only after recognition
   detected speech, so "what are the documents" became "documents". Fix: start recording the
   instant the mic opens, independent of recognition.

3. **Domain terms were mis-heard** (`GDPR → GTPL`, `16 → 60`). Fix: Whisper as the accurate
   final pass **plus** a corpus-derived vocabulary bias prompt, **plus** cleaner capture
   (`echoCancellation` / `noiseSuppression` / `autoGainControl`, mono, 128 kbps).

4. **LLM rate limits during eval** — Groq's free-tier 70B model has a ~100k tokens/day cap,
   and one full eval run ≈ that budget, so runs kept dying with 429s. Fix: refactored to a
   **provider-agnostic OpenAI-compatible client** and moved to **Cerebras `gpt-oss-120b`**
   (very fast, generous tier). Hit a second wall — the Cerebras tier didn't serve
   `llama-3.3-70b`, so I queried `/models` and standardised on `gpt-oss-120b`. The provider
   is now a 3-line `.env` change.

5. **Robotic TTS** — the browser voice sounded synthetic. Fix: **Cartesia `sonic-2`** with an
   auto-selected natural voice, browser TTS kept only as a fallback.

6. **The app looked frozen** — the whole pipeline (rewrite + search + verify) ran before any
   output, so a multi-second answer felt like a crash. Fix: stream **granular progress stages**
   over the WS + an animated thinking indicator.

7. **Audio lagged the text** — the full answer was synthesised only after it had finished
   rendering. Fix: synthesise + play **per sentence** as chunks stream.

8. **The transcript visibly "autocorrected"** — users saw the live browser guess get
   overwritten by the Whisper result, which felt like their words were being changed. Fix:
   stop showing the jittery live preview; show a stable "Listening" indicator and then the
   accurate final transcript once.

9. **A React "invalid hook" crash** from a stray root-level `node_modules` (duplicate React) —
   fixed by keeping installs strictly inside `frontend/`.

---

## Resilience & persistence

- **Retry/backoff** (`tenacity`) on every LLM call (`app/llm/llm_client.py`).
- **Graceful audio handling** — empty/short/no-speech audio is dropped, not transcribed;
  Whisper failure falls back to the browser transcript; TTS failure falls back to browser
  voice.
- **Agent fallbacks** — tool-calling misfires fall back to direct retrieve-then-answer;
  malformed tool args fall back to the rewritten query.
- **Global exception handler** returns a clean 500 instead of leaking stack traces; the
  WebSocket reconnects with exponential backoff.
- **Persistence** — uploaded chunks + embeddings (Chroma) and conversation history (SQLite)
  are written to disk under `backend/storage/` and **survive a restart**.

---

## Prompt design

- **Rewrite prompt** turns a spoken, context-dependent question into one standalone search
  query (single line), using the summary + recent turns.
- **Answer prompt** constrains the model to the retrieved passages, requires `[n]` citations,
  permits the `list_documents` tool for corpus/metadata questions, and mandates an explicit
  "I don't know" when unsupported.
- **Verify prompt** is adversarial by design: it assumes claims are unsupported until a
  passage proves them, and treats same-fact disagreement as `conflict` rather than choosing.

---

## Tech stack

- **Backend:** FastAPI + Uvicorn, WebSocket streaming, keys held server-side
- **LLM:** any OpenAI-compatible endpoint via `openai` SDK — **Cerebras `gpt-oss-120b`** by
  default (answer + verify + rewrite); swap to Groq/OpenRouter/Together/Ollama in `.env`
- **STT:** Groq **Whisper `whisper-large-v3-turbo`** (final) + browser Web Speech (interim/barge-in)
- **TTS:** **Cartesia `sonic-2`** (browser `speechSynthesis` fallback)
- **Embeddings:** `fastembed` local **`BAAI/bge-small-en-v1.5`** (warmed on startup)
- **Retrieval:** Chroma (dense) + `rank_bm25` (sparse) + RRF + cross-encoder rerank
- **Storage:** Chroma (vectors) + SQLite (chunks, conversations, messages)
- **Frontend:** React 19 + Vite + TypeScript + React Router

---

## Setup

**Backend**

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set LLM_API_KEY (Cerebras), STT_API_KEY (Groq), CARTESIA_API_KEY
uvicorn app.main:app --reload   # http://127.0.0.1:8000
```

**Frontend**

```bash
cd frontend && npm install && npm run dev   # http://localhost:5173 (proxies API + WS to :8000)
```

Open `http://localhost:5173/`. Use **Chrome or Edge** for voice (Web Speech API).
Without the Cartesia/Whisper keys the app still runs on the browser's built-in STT/TTS.

---

## Sample corpus (real, conflicting data)

`backend/eval/fixtures/` holds **real public privacy-law text**, chosen because the sources
genuinely overlap *and* conflict:

- **GDPR** Articles 7, 8, 17, 33, 83 (verbatim, gdpr-info.eu)
- **CCPA** consumer rights (California AG) + statutory thresholds/penalties
- **Original 2018 CCPA** vs the **CPRA-amended** version — these contradict on the
  consumer-count threshold (**50,000 → 100,000**), the deliberate conflict used to test
  conflict surfacing.

The running app never pre-loads these; it only answers over what *you* upload. They exist for
a reproducible demo and eval.

---

## Limitations & future work

- **Model-independent conflict detection** — a dedicated claim-pair contradiction checker so
  conflict surfacing doesn't depend on the answering model's reasoning.
- **Lower time-to-first-word** — stream the draft answer token-by-token (currently the
  verified answer is streamed after verification, trading latency for never speaking an
  ungrounded claim).
- **Hierarchical/semantic chunking + metadata filtering** for larger, messier corpora.
- **Web Speech quality varies** by browser/accent; a fully server-side streaming STT would be
  more consistent.

---

## Project structure

```
backend/
  app/
    ingestion/   parse + structure-aware chunk + ingest service
    embeddings/  fastembed wrapper (warmed on startup)
    retrieval/   hybrid search, BM25, RRF, cross-encoder rerank, cache
    agent/       orchestrator, verify, memory, prompts, tools, guards
    routes/      documents, search, ask, conversations, transcribe, tts, voice_ws
    store/       db, repository, vector_store
    llm/         provider-agnostic LLM client, Whisper STT, Cartesia TTS
  eval/          run_eval.py, qa_pairs.yaml, fixtures/, REPORT.md
frontend/
  src/
    pages/       LandingPage
    components/  DemoPlayer, UploadPanel, ConversationView, SourcePanel, VoiceConsole
    lib/         api, speech (STT capture/TTS playback/VAD/barge-in), voiceClient (WS)
```
