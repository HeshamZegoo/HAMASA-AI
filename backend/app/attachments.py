import base64
import io
import logging
from typing import Literal

from pydantic import BaseModel, Field

logger = logging.getLogger("hamasa.attachments")

MAX_FILE_BYTES = 64 * 1024 * 1024
TEXT_TYPES = {
    "text/plain", "text/markdown", "text/csv", "application/json",
    "application/xml", "text/xml"
}
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

class AttachmentInput(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    mime_type: str = Field(min_length=1, max_length=120)
    data: str = Field(min_length=1, max_length=90_000_000)

def _decode(item: AttachmentInput) -> bytes:
    try:
        raw = base64.b64decode(item.data, validate=True)
    except Exception as exc:
        raise ValueError(f"الملف {item.name} تالف أو مش بصيغة Base64 صحيحة.") from exc
    if not raw or len(raw) > MAX_FILE_BYTES:
        raise ValueError(f"حجم الملف {item.name} غير مسموح. الحد الأقصى 8 ميجابايت.")
    return raw

def _extract_text(item: AttachmentInput, raw: bytes) -> str:
    mime = item.mime_type.lower()
    suffix = item.name.rsplit(".", 1)[-1].lower() if "." in item.name else ""
    if mime in TEXT_TYPES or suffix in {"txt", "md", "csv", "json", "xml", "log", "py", "js", "html", "css"}:
        return raw.decode("utf-8-sig", errors="replace")
    if mime == "application/pdf" or suffix == "pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            return "\n".join(page.extract_text() or "" for page in reader.pages[:40])[:50000]
        except Exception as exc:
            logger.info("PDF extraction failed for %s: %s", item.name, type(exc).__name__)
            raise ValueError(f"مقدرتش أقرأ محتوى PDF: {item.name}.") from exc
    if mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or suffix == "docx":
        try:
            from docx import Document
            doc = Document(io.BytesIO(raw))
            return "\n".join(p.text for p in doc.paragraphs)[:50000]
        except Exception as exc:
            logger.info("DOCX extraction failed for %s: %s", item.name, type(exc).__name__)
            raise ValueError(f"مقدرتش أقرأ ملف Word: {item.name}.") from exc
    raise ValueError(f"نوع الملف {item.name} غير مدعوم حالياً.")

def prepare_messages(messages, attachments, model):
    prepared = [{"role": m.role, "content": m.content} for m in messages if m.role in ("user", "assistant")]
    if len(prepared) > 40:
        prepared = prepared[-40:]
    if not attachments:
        return prepared

    text_parts = []
    image_parts = []
    for item in attachments:
        raw = _decode(item)
        mime = item.mime_type.lower().split(";")[0].strip()
        if mime in IMAGE_TYPES:
            image_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"}
            })
        else:
            extracted = _extract_text(item, raw)
            text_parts.append(f"\n\n--- محتوى الملف: {item.name} ---\n{extracted}")

    if text_parts or image_parts:
        if not prepared or prepared[-1]["role"] != "user":
            raise ValueError("لازم تبعت رسالة مع المرفقات.")
        last = prepared[-1]
        prompt = "المستخدم أرفق الملفات التالية. حلل محتواها واستخدمها في الإجابة، ولو طلب تلخيص أو استخراج معلومات نفّذ المطلوب."
        if text_parts:
            prompt += "".join(text_parts)
        if image_parts:
            prompt += "\n\nحلل الصور المرفقة بصرياً وأجب عن سؤال المستخدم بشأنها."
            last["content"] = [{"type": "text", "text": last["content"] + "\n\n" + prompt}] + image_parts
        else:
            last["content"] = last["content"] + "\n\n" + prompt
    return prepared
