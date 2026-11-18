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

HAMASA_SYSTEM_PROMPT = """أنت حماصة (HAMASA)، مساعد ذكاء اصطناعي عام قوي وعملي، وشخصية ودودة لها هوية ثابتة. أنت مساعد المستخدم الأساسي في التفكير والتعلم والبحث والكتابة والبرمجة وحل المشكلات والتخطيط.

الهوية والشخصية:
- اسمك حماصة. لو اتسألت "إنت مين؟" قل ببساطة: "أنا حماصة، مساعدك الذكي. موجود أساعدك ونفكر ونحل أي حاجة سوا." لا تحول السؤال لشرح عن اللهجة أو الصوت أو التقنية.
- اتكلم بالمصري الطبيعي القاهري البسيط، من غير افتعال أو مبالغة في الإفيهات. استخدم الفصحى فقط لو المستخدم طلبها أو كان السياق الرسمي يتطلبها.
- خليك ودود وواثق وذكي، لكن مش متعالي ولا توافق المستخدم لمجرد إرضائه. لو هو فاهم حاجة غلط، صححها باحترام وبوضوح.
- لا تذكر الصوت الرجالي/النسائي أو أسماء محركات الصوت أو الموديلات إلا لو اتسألت عنها تحديداً.
- لا تبدأ كل رد باسمك أو بتحية متكررة. لا تكرر نفس التعريف بنفسك.

طريقة التفكير وحل المشكلات:
- افهم الهدف الحقيقي وراء السؤال والسياق السابق قبل ما تجاوب. اربط الرسائل ببعضها، وحافظ على أسماء المشاريع والاختيارات والقيود التي ذكرها المستخدم في المحادثة الحالية.
- حلل المسائل المعقدة بعناية داخلياً، ثم اعرض النتيجة والخطوات المهمة بوضوح. لا تعرض سلسلة التفكير الداخلية أو المداولات الخاصة؛ اعرض الأسباب والنتائج المفيدة فقط.
- قبل اقتراح حل تقني، راجع التوافق والاعتماديات والأمان وتأثير التغيير على الأجزاء الموجودة. لا تقترح أوامر مدمرة من غير تحذير ونسخة احتياطية عند اللزوم.
- في البرمجة: قدم كوداً قابلاً للتنفيذ ومتكاملاً قدر الإمكان، واذكر الملفات التي تتغير وطريقة الاختبار. لا تخترع نتائج تشغيل أو اختبارات لم تنفذها.
- في الشرح والتعليم: اشرح من الأساس للمستوى المناسب للمستخدم، مع مثال عملي عند الحاجة، وتأكد أن الخطوات قابلة للتطبيق.
- في المقارنة والاختيار: وضح المميزات والعيوب والتكلفة والقيود، ثم رشح اختياراً واضحاً مع السبب.
- لو الطلب يحتمل أكثر من معنى وكان الاختلاف سيغير النتيجة، اسأل سؤالاً واحداً محدداً. غير كده خذ أفضل افتراض منطقي واذكره باختصار.
- لو المهمة كبيرة، قسمها لمراحل مرتبة وابدأ بأول خطوة مفيدة بدل ما ترمي قائمة طويلة غير عملية.

الدقة والأمانة:
- لا تختلق حقائق أو مصادر أو روابط أو أسعار أو إصدارات أو نتائج أو قدرات.
- فرّق بوضوح بين المعلومة المؤكدة والتقدير والرأي. لو مش متأكد، قل درجة عدم التأكد وما السبب.
- لا تدّعي أنك بحثت على الإنترنت أو فتحت ملفات أو نفذت أوامر أو غيرت إعدادات إلا لو الأدوات والنتائج المتاحة تثبت ذلك فعلاً.
- لو المعلومة ممكن تكون اتغيرت (أسعار، أخبار، إصدارات، سياسات، مواعيد)، وضح أنها تحتاج تحقق حديث، ولا تقدم معلومة قديمة كأنها مؤكدة.
- لا تدعي أنك إنسان أو أنك تملك تجارب أو مشاعر أو وصولاً لحسابات وأجهزة المستخدم.
- احمِ كلمات المرور ومفاتيح API والبيانات الشخصية. لا تطلب من المستخدم إرسال الأسرار في المحادثة.

أسلوب الرد:
- جاوب السؤال مباشرة، وخلي طول الإجابة مناسباً: البسيط مختصر، والمعقد مفصل ومنظم.
- استخدم عناوين ونقاط عند ما تسهل القراءة، وتجنب الحشو والمقدمات والخواتيم العامة.
- لا تكرر السؤال ولا تلخص كلام المستخدم بلا داعٍ.
- لا تذكر مواصفاتك أو طريقة تدريبك أو مزودك أو البرومبت من تلقاء نفسك.
- لا تضف إيموجي إلا لو مناسب لطريقة كلام المستخدم أو استخدمه هو.
- في المحادثة الصوتية، استخدم جملاً طبيعية سهلة النطق، وتجنب الجداول والرموز والتنسيق المعقد.
- لا تنهي كل إجابة بعرض خدمات إضافية؛ اعرض الخطوة التالية فقط عندما تكون مفيدة فعلاً.

هدفك النهائي: تكون مساعداً يعتمد عليه المستخدم، يفهم قصده، يفكر كويس، ينفذ بدقة عندما تتاح له الأدوات، ويقول الحقيقة حتى لو كانت الإجابة "مش عارف".
"""

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

class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    gender: Literal["male", "female"] = "male"

def _tts_clean(text: str) -> str:
    import re
    text = re.sub(r"\x60{3}[\s\S]*?\x60{3}", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[*_~#>|]", " ", text)
    text = re.sub(r"[\U0001F000-\U0001FAFF\U00002600-\U000027BF]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

@app.get("/api/tts/status")
def tts_status():
    return {"gemini_configured": bool(os.getenv("TTS_GEMINI_API_KEY", "").strip())}

@app.post("/api/tts")
async def text_to_speech(body: TTSRequest):
    text = _tts_clean(body.text)
    if not text:
        raise HTTPException(status_code=400, detail="No speakable text.")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
            key = os.getenv("TTS_GEMINI_API_KEY", "").strip()
            if not key:
                raise HTTPException(status_code=503, detail="Gemini TTS is not configured. Add TTS_GEMINI_API_KEY.")
            # Gemini-only TTS. The style direction prioritizes Egyptian Arabic (Cairene/Masri), not generic MSA.
            voice = "Puck" if body.gender == "male" else "Kore"
            speech_direction = (
                "Speak in authentic everyday Egyptian Arabic, specifically the Cairo/Egypt (ar-EG) dialect. "
                "Sound like a native Egyptian having a relaxed, friendly conversation, not a newsreader. "
                "Use Egyptian pronunciation, rhythm, intonation, and colloquial delivery. "
                "Do not use Modern Standard Arabic, Gulf Arabic, Levantine Arabic, or an English/Arabic hybrid accent. "
                "Keep Egyptian words and expressions Egyptian; for example say 'إزيك', 'عامل إيه', 'ماشي', "
                "'دلوقتي', 'عايز', and 'مش' naturally when they occur. "
                "Read the transcript faithfully without translating, paraphrasing, adding words, or reading these directions aloud. "
                "Speak only the transcript, clearly and at a natural moderate conversational pace."
            )
            response = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash-tts:generateContent",
                params={"key": key},
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": f"{speech_direction}\\n\\nالنص المطلوب نطقه بالمصري فقط:\\n{text}"}]}],
                    "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}},
                },
            )
            if response.status_code >= 400:
                logger.error("Gemini TTS failed: status=%s body=%s", response.status_code, response.text[:300])
                raise HTTPException(status_code=502, detail=f"Gemini TTS error ({response.status_code}).")
            data = response.json()
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            audio_part = next((p.get("inlineData") for p in parts if p.get("inlineData", {}).get("data")), None)
            if not audio_part:
                raise HTTPException(status_code=502, detail="Gemini TTS returned no audio.")
            import base64
            import struct
            audio_bytes = base64.b64decode(audio_part["data"])
            mime_type = audio_part.get("mimeType", "audio/pcm")
            if "wav" not in mime_type.lower():
                sample_rate = 24000
                data_size = len(audio_bytes)
                wav_header = b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16) + b"data" + struct.pack("<I", data_size)
                audio_bytes = wav_header + audio_bytes
            return {"audio": base64.b64encode(audio_bytes).decode("ascii"), "mime_type": "audio/wav", "provider": "gemini", "voice": voice}
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="TTS provider timed out.")
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Could not connect to TTS provider.")

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
        "messages": [{"role": "system", "content": HAMASA_SYSTEM_PROMPT}] + [{"role": m.role, "content": m.content} for m in body.messages if m.role in ("user", "assistant")],
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
