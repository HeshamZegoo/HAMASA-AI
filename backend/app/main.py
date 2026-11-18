import logging
import os
import sqlite3
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger("hamasa.provider")

APP_ENV = os.getenv("APP_ENV", "development")
API_KEY = os.getenv("AI_API_KEY", "").strip()
BASE_URL = os.getenv("AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
ORIGINS = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:8000,https://heshamzego.github.io").split(",") if x.strip()]

app = FastAPI(title="HAMASA AI API", version="0.1.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1, max_length=12000)

class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=40)

def init_db():
    if DATABASE_URL.startswith("sqlite:///"):
        path = DATABASE_URL.removeprefix("sqlite:///")
    elif not DATABASE_URL:
        path = str(Path(__file__).resolve().parent.parent / "hamasa.db")
    else:
        # PostgreSQL persistence is provisioned separately; do not silently pretend SQLite is PostgreSQL.
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE IF NOT EXISTS conversations (id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP, title TEXT NOT NULL)")
        db.commit()

@app.on_event("startup")
def startup():
    init_db()

@app.get("/")
def root():
    return {"name": "HAMASA AI API", "status": "online", "docs": "/docs"}

@app.get("/health")
def health():
    return {"status": "ok", "provider_configured": bool(API_KEY), "model": MODEL}

@app.post("/api/chat")
async def chat(body: ChatRequest):
    if not API_KEY:
        raise HTTPException(status_code=503, detail="AI provider is not configured. Set AI_API_KEY in the backend environment.")

    payload = {
        "model": MODEL,
        "messages": [{"role": m.role, "content": m.content} for m in body.messages],
        "temperature": 0.7,
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=15.0)) as client:
            response = await client.post(
                f"{BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json=payload,
            )

        if response.status_code >= 400:
            provider_message = "AI provider rejected the request."
            try:
                error_data = response.json()
                if isinstance(error_data, dict):
                    error_obj = error_data.get("error")
                    if isinstance(error_obj, dict):
                        provider_message = str(error_obj.get("message") or error_obj.get("detail") or provider_message)
                    elif isinstance(error_obj, str):
                        provider_message = error_obj
                    else:
                        provider_message = str(error_data.get("detail") or error_data.get("message") or provider_message)
            except (ValueError, TypeError):
                pass

            # Log only provider status and its error message; never log API keys or chat prompts.
            logger.error("Provider request failed: status=%s model=%s message=%s",
                         response.status_code, MODEL, provider_message[:500])
            raise HTTPException(status_code=502, detail=f"AI provider error ({response.status_code}): {provider_message[:500]}")

        try:
            data = response.json()
            reply = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            logger.error("Provider returned an unexpected success payload: status=%s model=%s",
                         response.status_code, MODEL)
            raise HTTPException(status_code=502, detail="AI provider returned an unexpected response format.")

        if not isinstance(reply, str) or not reply.strip():
            raise HTTPException(status_code=502, detail="AI provider returned an empty response.")

        return {"reply": reply.strip(), "model": MODEL}

    except httpx.TimeoutException:
        logger.exception("Provider request timed out: model=%s", MODEL)
        raise HTTPException(status_code=504, detail="AI provider timed out. Try again.")
    except httpx.RequestError as exc:
        logger.error("Provider connection failed: type=%s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Could not connect to the AI provider.")
