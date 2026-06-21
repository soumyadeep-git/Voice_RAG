# Ask My Notes

A voice-enabled, grounded document Q&A agent. Upload a small set of documents and have a real-time spoken conversation about them, where every answer is retrieved, verified against the sources, and cited, with conflicts between documents surfaced rather than hidden.

## Stack

- Backend: FastAPI (Python)
- LLM: Groq (`llama-3.3-70b-versatile`, `llama-3.1-8b-instant`)
- Embeddings: `fastembed` (local, `BAAI/bge-small-en-v1.5`)
- Vector store: Chroma + BM25 hybrid retrieval
- Voice: browser Web Speech API (STT/TTS), Groq Whisper fallback
- Frontend: React + Vite + TypeScript

## Setup

1. `cd backend && python3 -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. `cp .env.example .env` and set `GROQ_API_KEY`
4. `uvicorn app.main:app --reload`
5. Frontend setup follows in a later step.

## Status

Work in progress, built in incremental rounds. See the plan and commit history.
