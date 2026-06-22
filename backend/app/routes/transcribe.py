from fastapi import APIRouter, HTTPException, UploadFile

from app.llm.stt import STTUnavailableError, transcribe

router = APIRouter(prefix="/transcribe", tags=["voice"])

MAX_BYTES = 25 * 1024 * 1024


@router.post("")
async def transcribe_audio(audio: UploadFile) -> dict:
    raw = await audio.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty audio")
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="audio too large")
    try:
        text = transcribe(raw, audio.filename or "audio.webm")
    except STTUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"text": text}
