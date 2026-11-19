"""Small, deterministic relevance filter for account-scoped saved memories."""

import re
from math import.sqrt
from typing import Any


_TOKEN = re.compile(r"[a-z0-9_+#.-]{2,}|[\u0600-\u06ff]{2,}", re.IGNORECASE)
_ARABIC_NORMALIZATION = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي",
})
_STOP_WORDS = {
    "the", "and", "for", "with", "from", "that", "this", "what", "when",
    "where", "which", "who", "how", "are", "was", "were", "you", "your",
    "about", "please", "can", "could", "would", "should", "into", "على",
    "في", "من", "عن", "الى", "إلى", "ده", "دي", "دا", "ده", "ايه", "ما",
    "هو", "هي", "انا", "انت", "انتي", "احنا", "هم", "مع", "بعد", "قبل",
    "عايز", "عاوزه", "ممكن", "لو", "بس", "كل", "اي", "أي", "هذا", "هذه",
}


def _tokens(value: str) -> set[str]:
    normalized = str(value or "").lower().translate(_ARABIC_NORMALIZATION)
    return {token for token in _TOKEN.findall(normalized) if token not in _STOP_WORDS}


def select_relevant_memories(
    memories: list[dict[str, Any]],
    query: str,
    *,
    max_items: int = 6,
    max_chars: int = 2400,
) -> list[dict[str, str]]:
    """Return a bounded, relevance-ranked subset; unrelated memories are omitted.

    This is deliberately deterministic and dependency-free. It is a lightweight
    lexical filter, not semantic search; ambiguous queries safely retrieve none.
    """
    query_tokens = _tokens(query)
    if not query_tokens or max_items <= 0 or max_chars <= 0:
        return []

    ranked: list[tuple[float, int, dict[str, str]]] = []
    for index, memory in enumerate(memories or []):
        if not isinstance(memory, dict):
            continue
        text = str(memory.get("text") or "").strip()[:500]
        category = str(memory.get("category") or "").strip()
        if not text or category not in {"preference", "project", "decision", "temporary"}:
            continue
        memory_tokens = _tokens(text)
        overlap = query_tokens & memory_tokens
        if not overlap:
            continue
        # Cosine-like overlap penalizes generic matches against long memories.
        score = len(overlap) / sqrt(len(query_tokens) * max(1, len(memory_tokens)))
        item = {"category": category, "text": text}
        ranked.append((score, index, item))

    ranked.sort(key=lambda entry: (-entry[0], entry[1]))
    selected: list[dict[str, str]] = []
    used_chars = 0
    for _, _, item in ranked:
        cost = len(item["text"]) + len(item["category"]) + 4
        if used_chars + cost > max_chars:
            continue
        selected.append(item)
        used_chars += cost
        if len(selected) >= max_items:
            break
    return selected
