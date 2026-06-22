# Demo Video Script — Ask My Notes

Target length: **~3–4 minutes**. Use Chrome/Edge. Have the backend (`:8000`) and frontend (`:5173`) running, and the `backend/eval/fixtures/` files ready to upload. Run the demo with the **70B** model configured so conflict detection works live.

---

## 0:00 — Landing page (15s)
- Open `http://localhost:5173/`.
- **Say:** "This is *Ask My Notes*, a voice-enabled agent that answers questions about your own documents — grounded, cited, and honest about what it doesn't know."
- Click ▶ on the demo player to show the 10-second walkthrough, then click **Launch the app**.

## 0:15 — Upload (20s)
- Drag the GDPR and CCPA files from `backend/eval/fixtures/` into the upload panel.
- **Say:** "I'm uploading real GDPR and CCPA legal text. These overlap on privacy rights but disagree on specifics — perfect for testing grounding and conflict handling. The app parses, chunks, embeds, and indexes them; nothing is pre-loaded."
- Wait for the badges to turn **ready**.

## 0:35 — Grounded, cited answer (35s)
- Press the mic. **Ask:** "Under the GDPR, can a child under sixteen consent to data processing on their own?"
- **Point out:** the spoken + on-screen answer, the `[1]` citation, the green **GROUNDED** badge, and the exact passage (filename + section) in the sources panel.
- **Say:** "Every claim is verified against the source before it's spoken, and cited to the exact passage."

## 1:10 — Multi-turn memory (25s)
- **Ask (follow-up):** "And what about a child under thirteen?"
- **Say:** "Notice it understood 'a child under thirteen' in the context of the previous question — it keeps bounded conversation memory across turns."

## 1:35 — Conflict surfacing (40s)
- **Ask:** "How many consumers must a business handle annually to fall under the CCPA?"
- **Point out:** the answer states **both** values — 50,000 in the original 2018 act and 100,000 after the CPRA amendment — and the **CONFLICT** badge.
- **Say:** "The original and amended CCPA genuinely contradict each other here. Instead of silently picking one, the agent surfaces the conflict and cites both sources."

## 2:15 — Refusal / honesty (25s)
- **Ask:** "What is India's data protection law called?"
- **Say:** "That isn't in the uploaded documents, so it refuses rather than hallucinating — 'I don't know based on the uploaded documents.'"

## 2:40 — Barge-in / interruption (25s)
- **Ask** a longer question (e.g. "What rights does the CCPA give California consumers?"), and **while it's speaking, talk over it** with: "Actually, what's the GDPR breach notification deadline?"
- **Say:** "I can interrupt mid-answer — speaking cancels playback instantly and the agent switches to the new question. That's the real-time, interruptible loop."

## 3:05 — Evaluation & wrap (40s)
- Show `backend/eval/REPORT.md` and `eval/qa_pairs.yaml`.
- **Say:** "An evaluation harness scores the system on a labelled set — answerable, multi-source, conflict, and unanswerable questions — reporting retrieval hit-rate, groundedness, refusal accuracy, and conflict detection. It also surfaced a real finding: conflict detection needs the larger model, while the smaller one is fine for straightforward answers and refusals."
- **Close:** "Hybrid retrieval, an agentic loop, a strict verification pass, multi-turn memory, and a real-time voice interface — all grounded in the user's own documents."

---

### Quick reference — questions used
1. "Under the GDPR, can a child under sixteen consent to data processing on their own?" → grounded + cited
2. "And what about a child under thirteen?" → memory / follow-up
3. "How many consumers must a business handle annually to fall under the CCPA?" → conflict (50k vs 100k)
4. "What is India's data protection law called?" → refusal
5. "What rights does the CCPA give California consumers?" (interrupt with) "Actually, what's the GDPR breach notification deadline?" → barge-in
