import unittest

from backend.app.quality import coding_instructions_for


class CodingGuidanceTests(unittest.TestCase):
    def guidance(self, text):
        return coding_instructions_for([{"role": "user", "content": text}])

    def test_english_coding_request_gets_guidance(self):
        result = self.guidance("Debug this Python traceback")
        self.assertIn("السبب الجذري", result)
        self.assertIn("اختبارات", result)

    def test_egyptian_arabic_coding_request_gets_guidance(self):
        self.assertTrue(self.guidance("عايز تصلحلي خطأ في الكود"))

    def test_tooling_and_framework_requests_get_guidance(self):
        self.assertTrue(self.guidance("Help me fix this npm and Vite build"))
        self.assertTrue(self.guidance("راجعلي اختبارات المشروع"))

    def test_html_and_website_requests_get_coding_guidance(self):
        self.assertIn("صفحة أو تطبيق ويب", self.guidance("عايز تعمللي صفحة ويب"))
        self.assertTrue(self.guidance("Create a website for my portfolio"))

    def test_normal_chat_does_not_get_coding_guidance(self):
        self.assertEqual(self.guidance("عامل إيه النهارده؟"), "")

    def test_only_latest_user_turn_controls_detection(self):
        result = coding_instructions_for([
            {"role": "user", "content": "Help me with Python"},
            {"role": "assistant", "content": "Sure"},
            {"role": "user", "content": "What is the capital of Japan?"},
        ])
        self.assertEqual(result, "")

    def test_latest_user_turn_is_found_after_assistant_messages(self):
        result = coding_instructions_for([
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "A language."},
            {"role": "user", "content": "Fix my API endpoint"},
        ])
        self.assertTrue(result)

    def test_non_text_multimodal_parts_are_ignored_safely(self):
        result = coding_instructions_for([
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
                {"type": "text", "text": "اشرحلي الخطأ في الكود"},
            ]},
        ])
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
