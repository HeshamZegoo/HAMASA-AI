import asyncio
import io
import os
import re
import time
import wave
from collections import defaultdict, deque

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi import Request
from pydantic import BaseModel, Field
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API_KEY = os.getenv("AI_API_KEY", "").strip()
BASE_URL = os.getenv("AI_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
MODEL = os.getenv("AI_MODEL", "nvidia/nemotron-3-super-120b-a12b")
ASR_FUNCTION_ID = "b702f636-f60c-4a3d-a6f4-f3568c13bd7d"
TTS_URL = "https://877104f7-e885-42b9-8de8-f6e4c6303969.invocation.api.nvcf.nvidia.com/v1/audio/synthesize"
SYSTEM = (
    "أنت حماصة، مساعد صوتي ذكي وودود. اتكلم باللهجة المصرية القاهرية الطبيعية، "
    "مش بالفصحى. خلي ردك مختصر وتلقائي كأنك بتتكلم مع صاحبك. "
    "ما تقراش إيموجي أو رموز أو تنسيق. لو السؤال محتاج شرح، اشرحه ببساطة وبالمصري."
)

app = FastAPI(title="HAMASA NVIDIA Voice Lab")
_rate = defaultdict(deque)


@app.middleware("http")
async def limit_public_requests(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown").split(",")[0].strip()
        now = time.monotonic()
        bucket = _rate[ip]
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= 18:
            return JSONResponse(status_code=429, content={"detail": "طلبات كتير بسرعة. استنى دقيقة وجرب تاني."})
        bucket.append(now)
    return await call_next(request)


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    voice: str = Field(pattern="^(male|female)$")


@app.get("/")
async def index():
    return FileResponse(ROOT / "index.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "nvidia_key_configured": bool(API_KEY),
        "chat_model_configured": bool(MODEL),
        "asr": "parakeet-1.1b-rnnt-multilingual-asr",
        "tts": "magpie-tts-multilingual",
    }


def _transcribe_wav(audio: bytes) -> str:
    try:
        import riva.client
    except ImportError as exc:
        raise RuntimeError("NVIDIA Riva client is not installed.") from exc

    auth = riva.client.Auth(
        uri="grpc.nvcf.nvidia.com:443",
        use_ssl=True,
        metadata_args=[
            ["function-id", ASR_FUNCTION_ID],
            ["authorization", f"Bearer {API_KEY}"],
        ],
    )
    service = riva.client.ASRService(auth)
    config = riva.client.RecognitionConfig(
        encoding=riva.client.AudioEncoding.LINEAR_PCM,
        sample_rate_hertz=16000,
        audio_channel_count=1,
        language_code="ar",
        max_alternatives=1,
        verbatim_transcripts=True,
        enable_automatic_punctuation=True,
    )
    result = service.offline_recognize(audio, config)
    parts = []
    for item in result.results:
        if item.alternatives:
            parts.append(item.alternatives[0].transcript)
    return " ".join(parts).strip()


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)):
    if not API_KEY:
        raise HTTPException(status_code=503, detail="NVIDIA API key is not configured.")
    audio = await file.read()
    if len(audio) < 1000 or len(audio) > 12_000_000:
        raise HTTPException(status_code=400, detail="التسجيل فاضي أو حجمه كبير.")
    try:
        with wave.open(io.BytesIO(audio), "rb") as wav:
            if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != 16000:
                raise HTTPException(status_code=400, detail="الصوت لازم يكون WAV أحادي القناة 16-bit وبتردد 16000.")
            pcm_audio = wav.readframes(wav.getnframes())
            if not pcm_audio:
                raise HTTPException(status_code=400, detail="التسجيل مفيهوش صوت صالح.")
    except wave.Error as exc:
        raise HTTPException(status_code=400, detail="ملف الصوت مش WAV صالح.") from exc
    try:
        text = await asyncio.to_thread(_transcribe_wav, pcm_audio)
    except HTTPException:
        raise
    except Exception as exc:
        print(f"NVIDIA ASR failed: {type(exc).__name__}: {str(exc)[:500]}", flush=True)
        raise HTTPException(status_code=502, detail="NVIDIA ASR تعذر عليه تحويل الصوت لنص.") from exc
    if not text:
        raise HTTPException(status_code=422, detail="ملحقتش أسمع كلام واضح. جرّب تاني.")
    return {"text": text, "provider": "nvidia-parakeet"}


@app.post("/api/chat")
async def chat(body: ChatRequest):
    if not API_KEY:
        raise HTTPException(status_code=503, detail="NVIDIA API key is not configured.")
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": body.text},
        ],
        "temperature": 0.65,
        "max_tokens": 450,
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(75, connect=12)) as client:
            response = await client.post(
                f"{BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json=payload,
            )
        if response.status_code >= 400:
            print(f"NVIDIA chat error {response.status_code}: {response.text[:700]}", flush=True)
            raise HTTPException(status_code=502, detail=f"NVIDIA chat API رفض الطلب ({response.status_code}).")
        data = response.json()
        answer = data["choices"][0]["message"]["content"]
        if isinstance(answer, list):
            answer = " ".join(str(p.get("text", "")) for p in answer if isinstance(p, dict))
        answer = re.sub(r"[*_#`]+", "", str(answer)).strip()
        return {"text": answer, "model": MODEL}
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="NVIDIA chat اتأخر في الرد.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="تعذر الاتصال بخدمة NVIDIA.") from exc
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="رد NVIDIA وصل بصيغة غير متوقعة.") from exc


@app.post("/api/tts")
async def tts(body: TTSRequest):
    if not API_KEY:
        raise HTTPException(status_code=503, detail="NVIDIA API key is not configured.")
    voice = "Magpie-Multilingual.AR-XA.Jason" if body.voice == "male" else "Magpie-Multilingual.AR-XA.Sofia"
    form = {
        "text": body.text,
        "language": "ar-XA",
        "voice": voice,
        "sample_rate_hz": "22050",
        "encoding": "LINEAR_PCM",
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(75, connect=12)) as client:
            response = await client.post(
                TTS_URL,
                headers={"Authorization": f"Bearer {API_KEY}"},
                data=form,
            )
        if response.status_code >= 400:
            print(f"NVIDIA TTS error {response.status_code}: {response.text[:700]}", flush=True)
            raise HTTPException(status_code=502, detail=f"NVIDIA Magpie TTS رفض الطلب ({response.status_code}).")
        if not response.content.startswith(b"RIFF"):
            raise HTTPException(status_code=502, detail="NVIDIA TTS رجّع ملف صوت غير صالح.")
        return Response(content=response.content, media_type="audio/wav", headers={"Cache-Control": "no-store"})
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="NVIDIA TTS اتأخر في توليد الصوت.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="تعذر الاتصال بخدمة NVIDIA TTS.") from exc
