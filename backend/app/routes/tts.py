from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.llm.tts import TTSUnavailableError, synthesize

router = APIRouter(prefix="/tts", tags=["voice"])


class TTSRequest(BaseModel):
    text: str


@router.post("")
def text_to_speech(req: TTSRequest) -> Response:
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="empty text")
    try:
        audio = synthesize(text)
    except TTSUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return Response(content=audio, media_type="audio/mpeg")
