import unittest

from backend.app.memory_retrieval import select_relevant_memories
from backend.app.main import ChatRequest


class RelevantMemoryRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.memories = [
            {"category": "project", "text": "HAMASA AI backend uses FastAPI and Railway."},
            {"category": "preference", "text": "The user prefers Egyptian Arabic responses."},
            {"category": "project", "text": "ZEGO Disk Health OS uses Debian live-build."},
            {"category": "temporary", "text": "A temporary appointment is scheduled for Friday."},
        ]

    def test_only_memories_related_to_latest_question_are_selected(self):
        selected = select_relevant_memories(self.memories, "Fix the HAMASA FastAPI backend")
        self.assertEqual([item["text"] for item in selected], [self.memories[0]["text"]])
        self.assertNotIn(self.memories[2]["text"], [item["text"] for item in selected])

    def test_arabic_query_matches_arabic_saved_memory(self):
        selected = select_relevant_memories(
            [{"category": "preference", "text": "الرد باللهجة المصرية"}],
            "عايز الرد باللهجة المصرية",
        )
        self.assertEqual(len(selected), 1)

    def test_unrelated_or_ambiguous_query_returns_no_memory(self):
        self.assertEqual(select_relevant_memories(self.memories, "تمام شكرا"), [])
        self.assertEqual(select_relevant_memories(self.memories, ""), [])

    def test_results_are_bounded_by_count_and_character_budget(self):
        selected = select_relevant_memories(
            [{"category": "project", "text": "python " + ("backend " * 20)} for _ in range(10)],
            "python backend",
            max_items=2,
            max_chars=500,
        )
        self.assertLessEqual(len(selected), 2)
        self.assertLessEqual(sum(len(item["text"]) + len(item["category"]) + 4 for item in selected), 500)

    def test_chat_request_accepts_structured_memories_and_legacy_memory(self):
        request = ChatRequest(
            messages=[{"role": "user", "content": "Fix HAMASA"}],
            memory="legacy context",
            saved_memories=[{
                "category": "project",
                "text": "HAMASA backend uses FastAPI",
                "updated_at": "2026-11-19T12:00:00Z",
            }],
        )
        self.assertEqual(request.memory, "legacy context")
        self.assertEqual(request.saved_memories[0].category, "project")

    def test_invalid_categories_and_empty_memories_are_ignored(self):
        selected = select_relevant_memories(
            [{"category": "secret", "text": "python backend"}, {"category": "project", "text": ""}],
            "python backend",
        )
        self.assertEqual(selected, [])


if __name__ == "__main__":
    unittest.main()
