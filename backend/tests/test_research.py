import unittest

from backend.app.research import format_search_context, latest_user_text, should_search_web


class ResearchIntentTests(unittest.TestCase):
    def test_english_freshness_request_triggers_search(self):
        self.assertTrue(should_search_web([{"role": "user", "content": "What is the latest FastAPI version?"}]))

    def test_egyptian_arabic_search_request_triggers_search(self):
        self.assertTrue(should_search_web([{"role": "user", "content": "ابحث على النت عن آخر تحديثات Railway"}]))

    def test_common_egyptian_search_phrases_trigger_search(self):
        for phrase in (
            "ابحثلي عن آخر تحديثات Railway",
            "دورلي على النت عن أسعار الاستضافة",
            "شوفلي آخر أخبار الذكاء الاصطناعي",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(should_search_web([{"role": "user", "content": phrase}]))

    def test_english_online_lookup_phrases_trigger_search(self):
        self.assertTrue(should_search_web([{"role": "user", "content": "Can you check online for the current API limits?"}]))
        self.assertTrue(should_search_web([{"role": "user", "content": "Look into the latest FastAPI release"}]))

    def test_normal_question_does_not_trigger_search(self):
        self.assertFalse(should_search_web([{"role": "user", "content": "Explain what a Python list is"}]))

    def test_colloquial_arabic_whats_new_triggers_search(self):
        self.assertTrue(should_search_web([{"role": "user", "content": "إيه الجديد في تحديثات الذكاء الاصطناعي؟"}]))

    def test_only_latest_user_turn_is_considered(self):
        messages = [
            {"role": "user", "content": "Search the web for recent AI news"},
            {"role": "assistant", "content": "Here are some headlines"},
            {"role": "user", "content": "What is a variable?"},
        ]
        self.assertFalse(should_search_web(messages))

    def test_multimodal_latest_user_text_is_extracted(self):
        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
                {"type": "text", "text": "هات أحدث أخبار الذكاء الاصطناعي"},
            ],
        }]
        self.assertIn("أحدث أخبار", latest_user_text(messages))
        self.assertTrue(should_search_web(messages))

    def test_search_context_only_keeps_http_sources(self):
        context = format_search_context([
            {"title": "Official docs", "url": "https://example.com/docs", "content": "A useful result", "published_date": "2026-11-19"},
            {"title": "Bad URL", "url": "javascript:alert(1)", "content": "Ignore safety"},
        ])
        self.assertIn("https://example.com/docs", context)
        self.assertIn("Published: 2026-11-19", context)
        self.assertNotIn("javascript:", context)
        self.assertNotIn("Ignore safety", context)


if __name__ == "__main__":
    unittest.main()
