"""Voice API — Avira's ears and mouth.

POST /api/voice/transcribe   audio → text (local Whisper via transformers; lazy-loaded)
POST /api/voice/command      audio or text → Nexus actions + spoken reply (+ optional TTS)
POST /api/voice/tts          text → mp3 (ElevenLabs when configured; 204 → client falls back to browser TTS)
GET  /api/voice/capabilities what the server can do, so the client picks the right path
"""
from __future__ import annotations

import asyncio
import io
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import UserDB, get_session
from app.middleware.subscription_gate import check_rate_limit
from app.routes.auth import get_current_user
from app.routes.nexus import IngestRequest, ingest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/voice", tags=["voice"])

_asr = {"pipe": None, "error": None}


def _load_asr():
    if _asr["pipe"] or _asr["error"]:
        return _asr["pipe"]
    try:
        from transformers import pipeline  # type: ignore
        _asr["pipe"] = pipeline("automatic-speech-recognition", model=settings.whisper_model, chunk_length_s=30)
        logger.info(f"Whisper loaded: {settings.whisper_model}")
    except Exception as e:
        _asr["error"] = str(e)
        logger.warning(f"Whisper unavailable: {e}")
    return _asr["pipe"]


def _decode_audio(data: bytes):
    """Decode webm/ogg/wav/mp3 → float32 mono 16k using soundfile or torchaudio/ffmpeg."""
    try:
        import soundfile as sf  # type: ignore
        import numpy as np
        audio, sr = sf.read(io.BytesIO(data), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if sr != 16000:
            import torch, torchaudio  # type: ignore
            audio = torchaudio.functional.resample(torch.from_numpy(audio), sr, 16000).numpy()
        return {"raw": audio, "sampling_rate": 16000}
    except Exception:
        pass
    try:
        import torch, torchaudio  # type: ignore
        wav, sr = torchaudio.load(io.BytesIO(data))
        wav = wav.mean(dim=0)
        if sr != 16000:
            wav = torchaudio.functional.resample(wav, sr, 16000)
        return {"raw": wav.numpy(), "sampling_rate": 16000}
    except Exception as e:
        raise HTTPException(415, f"Unsupported audio format ({e}). Send 16k WAV or use browser speech recognition.")


async def transcribe_bytes(data: bytes) -> str:
    pipe = await asyncio.to_thread(_load_asr)
    if not pipe:
        raise HTTPException(503, {"error": "Server STT unavailable; use browser speech recognition.", "detail": _asr["error"]})
    audio = await asyncio.to_thread(_decode_audio, data)
    out = await asyncio.to_thread(pipe, audio)
    return (out.get("text") or "").strip()


class TTSRequest(BaseModel):
    text: str
    voice_id: Optional[str] = None


@router.get("/capabilities")
async def capabilities():
    return {
        "server_stt": _asr["pipe"] is not None or _asr["error"] is None,
        "server_tts": bool(settings.elevenlabs_api_key),
        "persona": {"name": "Avira", "accent": "en-GB", "style": "warm, precise, dry wit"},
        "wake_words": ["avira", "hey avira"],
    }


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...), user: UserDB = Depends(get_current_user)):
    text = await transcribe_bytes(await audio.read())
    return {"text": text}


@router.post("/command")
async def command(audio: Optional[UploadFile] = File(None), text: Optional[str] = Form(None), auto_apply: bool = Form(True),
                  speak: bool = Form(False), user: UserDB = Depends(check_rate_limit("voice")), db: AsyncSession = Depends(get_session)):
    if not text and audio is None:
        raise HTTPException(400, "Provide audio or text")
    transcript = text or await transcribe_bytes(await audio.read())
    if not transcript:
        return {"transcript": "", "reply": "I didn't catch that — could you say it again?", "actions": [], "event": None}
    result = await ingest(IngestRequest(text=transcript, source="voice", auto_apply=auto_apply), user, db)
    out = {"transcript": transcript, **result}
    if speak and settings.elevenlabs_api_key:
        try:
            mp3 = await _elevenlabs(out["reply"])
            import base64
            out["audio_b64"] = base64.b64encode(mp3).decode()
            out["audio_mime"] = "audio/mpeg"
        except Exception as e:
            logger.warning(f"TTS failed: {e}")
    return out


async def _elevenlabs(text: str, voice_id: Optional[str] = None) -> bytes:
    vid = voice_id or settings.elevenlabs_voice_id
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
                              headers={"xi-api-key": settings.elevenlabs_api_key, "accept": "audio/mpeg"},
                              json={"text": text[:2500], "model_id": "eleven_turbo_v2_5",
                                    "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.35}})
        r.raise_for_status()
        return r.content


@router.post("/tts")
async def tts(body: TTSRequest, user: UserDB = Depends(get_current_user)):
    if not settings.elevenlabs_api_key:
        return Response(status_code=204, headers={"X-TTS-Fallback": "browser"})
    try:
        mp3 = await _elevenlabs(body.text, body.voice_id)
    except Exception as e:
        raise HTTPException(502, f"TTS provider error: {e}")
    return StreamingResponse(io.BytesIO(mp3), media_type="audio/mpeg")
