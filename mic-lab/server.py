import os
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL = os.getenv("GEMINI_LIVE_MODEL", "models/gemini-3.8-live")
app = FastAPI(title="HAMASA Live Microphone Lab")
app.mount("/assets", StaticFiles(directory=ROOT / "assets"), name="assets") if (ROOT / "assets").exists() else None
_requests = defaultdict(deque)

class TokenRequest(BaseModel):
    voice: str = Field(pattern="^(male|female)$")

@app.get("/")
async def index():
    return FileResponse(ROOT / "index.html")

@app.get("/health")
async def health():
    return {"status": "ok", "gemini_key_configured": bool(API_KEY), "model": MODEL.removeprefix("models/")}

@app.post("/api/live-token")
async def live_token(body: TokenRequest, request: Request):
    if not API_KEY:
        raise HTTPException(status_code=503, detail="Gemini Live is not configured. Add GEMINI_API_KEY to this isolated Railway service.")
    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown").split(",")[0].strip()
    now_mono = time.monotonic()
    bucket = _requests[client_ip]
    while bucket and now_mono - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= 8:
        raise HTTPException(status_code=429, detail="Too many session requests. Wait one minute and try again.")
    bucket.append(now_mono)

    voice = "Puck" if body.voice == "male" else "Kore"
    now = datetime.now(timezone.utc)
    payload = {
        "uses": 1,
        "expireTime": (now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
        "newSessionExpireTime": (now + timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        "liveConnectConstraints": {
            "model": MODEL,
            "config": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
                "systemInstruction": {
                    "parts": [{
                        "text": (
                            "أنت حماصة، مساعد صوتي ذكي وودود. تحدث باللهجة المصرية القاهرية الطبيعية فقط، "
                            "بأسلوب محادثة تلقائي وواضح. افهم كلام المستخدم ورد عليه مباشرة، بإجابات طبيعية "
                            "ومختصرة غالباً. لا تقرأ الرموز أو التعليمات. لا تقل إنك نموذج ذكاء اصطناعي إلا إذا سُئلت. "
                            "استمع جيداً، ولا تقاطع المستخدم، وإذا قاطعك المستخدم توقف عن الكلام فوراً واستمع إليه."
                        )
                    }]
                },
                "inputAudioTranscription": {},
                "outputAudioTranscription": {}
            }
        }
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=10)) as client:
            response = await client.post(
                "https://generativelanguage.googleapis.com/v1alpha/auth_tokens",
                headers={"x-goog-api-key": API_KEY, "Content-Type": "application/json"},
                json=payload,
            )
        if response.status_code >= 400:
            # Log only the provider error payload for diagnosis; never log request headers or API keys.
            print(f"Gemini token API error {response.status_code}: {response.text[:1500]}", flush=True)
            raise HTTPException(status_code=502, detail=f"Gemini token service rejected the request ({response.status_code}).")
        data = response.json()
        token = data.get("name")
        if not isinstance(token, str) or not token.startswith("auth_tokens/"):
            raise HTTPException(status_code=502, detail="Gemini returned an invalid temporary token.")
        return {"token": token, "model": MODEL.removeprefix("models/"), "voice": voice}
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Gemini token request timed out.")
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Could not reach Gemini token service.")
