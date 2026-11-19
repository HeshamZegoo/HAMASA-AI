"""Task-aware quality guidance for HAMASA responses."""

import re
from typing import Any


_CODING_SIGNALS = re.compile(
    r"(?:\b(?:code|coding|program(?:ming)?|debug(?:ging)?|bug|traceback|exception|"
    r"stack\s*trace|function|class|method|api|sdk|sql|python|javascript|typescript|"
    r"react|html|css|bash|powershell|terminal|shell|git|github|docker|railway|node(?:\.js)?|npm|pnpm|yarn|vite|next\.js|fastapi|django|flask|pytest|unittest|linux|windows|macos|regex|regular\s+expression|algorithm|data\s+structure|refactor|review|pull\s+request|merge\s+conflict|"
    r"deploy(?:ment)?|compile|compiler|syntax|database|server|backend|frontend)\b)"
    r"|(?:كود|برمج(?:ة|ي|يات)|بايثون|جافاسكريبت|تايبسكريبت|ريأكت|دالة|كلاس|"
    r"خطأ في الكود|تصحيح|ديباج|ديباجنج|تيرمنال|طرفية|سطر أوامر|أوامر|"
    r"سيرفر|خادم|باك.?إند|فرونت.?إند|قاعدة بيانات|داتابيز|نشر المشروع|نود|npm|باكج|باكدج|باكدجات|اختبار(?:ات)?|خوارزمية|خوارزميات|هيكل بيانات|ريفاكتور|مراجعة كود|جيتهب|جيت هاب|لينكس|ويندوز|ماك|تعارض دمج|"
    r"ملف(?:ات)? المشروع|مشروع(?:ي)?|واجهة برمجية)",
    re.IGNORECASE,
)

CODING_GUIDANCE = """إرشادات متخصصة لمهام البرمجة والهندسة البرمجية:
- افهم المطلوب والبيئة والقيود أولاً. استخدم الملفات والكود والسياق المرفق فعلياً، ولا تفترض بنية مشروع أو إصدارات غير ظاهرة.
- حافظ على معمارية المشروع وأسماء الدوال والواجهات والتوافق الحالي. فضّل أصغر تعديل صحيح على إعادة كتابة واسعة.
- عند إصلاح خطأ: افصل العرض عن السبب الجذري، وتتبع مسار البيانات والاستدعاءات، وافحص الحالات الحدّية والتعامل مع الأخطاء قبل اقتراح التغيير.
- اكتب كوداً قابلاً للتشغيل، لا pseudo-code ولا دوال وهمية ولا TODOs، إلا إذا طلب المستخدم نموذجاً توضيحياً. لا تحذف أجزاء لازمة أو تستبدل ملفات كاملة بمقتطفات ناقصة.
- اذكر مسار الملف ومكان التغيير بوضوح. إذا طُلب ملف كامل فأعطِ الملف كاملاً؛ وإذا طُلب patch فاجعله محدوداً ودقيقاً.
- راعِ الأمان افتراضياً: تحقق من المدخلات والصلاحيات، استخدم parameterized queries، لا تكشف الأسرار، ولا تضع مفاتيح API في الواجهة أو السجلات.
- أضف أو حدّث اختبارات مناسبة. غطِّ النجاح والفشل والحالات الحدّية، وفكّر في التوافق والاعتماديات والأداء وإمكانية الوصول عند صلتها بالمهمة.
- لا تقل إن الكود اختُبر أو نُفّذ أو نُشر إلا إذا حدث ذلك فعلاً. عند غياب بيئة تشغيل، قل ما الذي راجعته وما الذي ما زال يحتاج اختباراً.
- لا تخترع أسماء دوال أو خيارات مكتبات أو أوامر CLI. إذا كانت التفاصيل تعتمد على إصدار أو API متغير، اطلب التحقق من توثيق موثوق حديث متى كانت أدوات البحث متاحة، أو صرّح بعدم اليقين.
- عند نقص معلومة غير حاسمة، اختر افتراضاً آمناً واذكره باختصار. اسأل سؤالاً واحداً فقط إذا كان النقص يمنع حلاً صحيحاً.
- اشرح القرار الهندسي المهم باختصار، ثم أعطِ خطوات تطبيق واختبار واضحة. لا تعرض التفكير الداخلي الخاص؛ اعرض النتيجة والأسباب القابلة للمراجعة فقط.
"""


def coding_instructions_for(messages: list[dict[str, Any]]) -> str:
    """Return coding-specific guidance only when the latest user turn is technical."""
    latest_user_text = ""
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content", "")
            if isinstance(content, str):
                latest_user_text = content
            elif isinstance(content, list):
                latest_user_text = " ".join(
                    str(part.get("text", "")) for part in content
                    if isinstance(part, dict) and part.get("type") in {"text", "input_text"}
                )
            break
    return CODING_GUIDANCE if _CODING_SIGNALS.search(latest_user_text) else ""
