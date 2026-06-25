import asyncio
import re
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.agent import guards, memory
from app.agent.orchestrator import answer_question
from app.llm.llm_client import LLMUnavailableError

router = APIRouter(tags=["voice"])

_SENTENCE = re.compile(r".+?(?:[.!?](?=\s|$)|\n|$)", re.DOTALL)


def _split_sentences(text: str) -> list[str]:
    parts = [m.group(0).strip() for m in _SENTENCE.finditer(text.strip())]
    return [p for p in parts if p]


@router.websocket("/ws")
async def voice_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    interrupt = asyncio.Event()
    queue: asyncio.Queue = asyncio.Queue()

    async def reader() -> None:
        try:
            while True:
                msg = await websocket.receive_json()
                kind = msg.get("type")
                if kind == "interrupt":
                    interrupt.set()
                elif kind == "ask":
                    await queue.put(msg)
        except (WebSocketDisconnect, RuntimeError, ValueError):
            await queue.put(None)

    reader_task = asyncio.create_task(reader())
    try:
        while True:
            msg = await queue.get()
            if msg is None:
                break
            interrupt.clear()
            await _handle_ask(websocket, msg, interrupt)
    except WebSocketDisconnect:
        pass
    finally:
        reader_task.cancel()


async def _handle_ask(websocket: WebSocket, msg: dict, interrupt: asyncio.Event) -> None:
    question = (msg.get("question") or "").strip()
    conv_id = memory.ensure_conversation(msg.get("conversation_id"))
    await _safe_send(websocket, {"type": "conversation", "conversation_id": conv_id})

    if not guards.is_meaningful(question):
        await _safe_send(websocket, {"type": "notice", "message": guards.NO_SPEECH_MESSAGE})
        await _safe_send(websocket, {"type": "status", "stage": "idle"})
        return
    if not guards.has_documents():
        await _send_simple(websocket, conv_id, question, guards.NO_DOCUMENTS_MESSAGE, "no_documents")
        return

    await _safe_send(websocket, {"type": "status", "stage": "thinking"})
    context = memory.load_context(conv_id)
    loop = asyncio.get_event_loop()

    def on_stage(stage: str) -> None:
        # Called from the executor thread; hop back onto the event loop to send.
        asyncio.run_coroutine_threadsafe(
            _safe_send(websocket, {"type": "status", "stage": stage}), loop
        )

    try:
        result = await loop.run_in_executor(
            None,
            lambda: answer_question(
                question, context["history"], context["summary"], on_stage=on_stage
            ),
        )
    except LLMUnavailableError as exc:
        await _safe_send(websocket, {"type": "error", "message": str(exc)})
        return
    except Exception:
        await _safe_send(
            websocket, {"type": "error", "message": "Failed to process the question"}
        )
        return

    await _safe_send(websocket, {"type": "rewritten", "query": result.rewritten_query})

    if interrupt.is_set():
        await _safe_send(websocket, {"type": "interrupted"})
        memory.record_turn(conv_id, question, result.answer, result.citations)
        return

    await _safe_send(websocket, {"type": "status", "stage": "answering"})
    interrupted = False
    for sentence in _split_sentences(result.answer):
        if interrupt.is_set():
            interrupted = True
            break
        await _safe_send(websocket, {"type": "answer_chunk", "text": sentence})
        await asyncio.sleep(0.02)

    memory.record_turn(conv_id, question, result.answer, result.citations)

    if interrupted:
        await _safe_send(websocket, {"type": "interrupted"})

    await _safe_send(
        websocket,
        {
            "type": "answer_complete",
            "answer": result.answer,
            "verification": result.verification,
            "citations": result.citations,
            "passages": result.passages,
            "tool_calls": result.tool_calls,
            "interrupted": interrupted,
        },
    )


async def _send_simple(
    websocket: WebSocket, conv_id: str, question: str, message: str, verdict: str
) -> None:
    await _safe_send(websocket, {"type": "status", "stage": "answering"})
    await _safe_send(websocket, {"type": "answer_chunk", "text": message})
    memory.record_turn(conv_id, question, message, [])
    await _safe_send(
        websocket,
        {
            "type": "answer_complete",
            "answer": message,
            "verification": {
                "verified_answer": message,
                "verdict": verdict,
                "grounded": False,
                "claims": [],
                "conflicts": [],
            },
            "citations": [],
            "passages": [],
            "tool_calls": [],
            "interrupted": False,
        },
    )


async def _safe_send(websocket: WebSocket, payload: dict) -> bool:
    try:
        await websocket.send_json(payload)
        return True
    except (WebSocketDisconnect, RuntimeError):
        return False
