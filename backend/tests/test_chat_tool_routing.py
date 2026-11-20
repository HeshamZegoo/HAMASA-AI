import base64
import os
import unittest
from unittest.mock import patch, AsyncMock

from fastapi import HTTPException
from pydantic import ValidationError

from backend.app import main


class FakeResponse:
    status_code = 200
    def json(self):
        return {"choices": [{"message": {"content": "تم التحليل بنجاح"}}]}


class FakeProviderClient:
    payloads = []
    def __init__(self, **kwargs):
        pass
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        return False
    async def post(self, url, headers=None, json=None):
        self.payloads.append(json)
        return FakeResponse()


class ChatRequestHistoryNormalizationTests(unittest.TestCase):
    def test_trims_oversized_historical_message_but_preserves_current_message(self):
        messages = [{"role": "user", "content": "old"} for _ in range(33)]
        messages.append({"role": "assistant", "content": "x" * 100_001})
        messages.append({"role": "user", "content": "current request"})

        request = main.ChatRequest(messages=messages)

        self.assertEqual(len(request.messages), 35)
        self.assertEqual(len(request.messages[33].content), 100_000)
        self.assertEqual(request.messages[-1].content, "current request")

    def test_still_rejects_oversized_current_message(self):
        with self.assertRaises(ValidationError):
            main.ChatRequest(messages=[{"role": "user", "content": "x" * 100_001}])

    def test_keeps_only_the_latest_40_messages_for_legacy_clients(self):
        messages = [{"role": "user", "content": f"message-{index}"} for index in range(41)]
        request = main.ChatRequest(messages=messages)
        self.assertEqual(len(request.messages), 40)
        self.assertEqual(request.messages[0].content, "message-1")
        self.assertEqual(request.messages[-1].content, "message-40")


class ChatToolRoutingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        FakeProviderClient.payloads = []

    async def test_image_message_uses_configured_vision_model(self):
        attachment = main.AttachmentInput(
            name="screen.png",
            mime_type="image/png",
            data=base64.b64encode(b"fake-image-bytes").decode("ascii"),
        )
        body = main.ChatRequest(
            messages=[main.Message(role="user", content="اشرح الصورة")],
            attachments=[attachment],
        )
        with patch.object(main, "API_KEY", "test-api-key"):
            with patch.object(main, "BASE_URL", "https://provider.example/v1"):
                with patch.dict(os.environ, {"AI_VISION_MODEL": "vision-test-model"}):
                    with patch("backend.app.main.httpx.AsyncClient", FakeProviderClient):
                        result = await main.chat(body)
        self.assertEqual(result["reply"], "تم التحليل بنجاح")
        self.assertEqual(FakeProviderClient.payloads[0]["model"], "vision-test-model")
        self.assertTrue(any(
            isinstance(message.get("content"), list)
            for message in FakeProviderClient.payloads[0]["messages"]
        ))

    async def test_image_request_fails_clearly_without_vision_model(self):
        attachment = main.AttachmentInput(
            name="screen.png",
            mime_type="image/png",
            data=base64.b64encode(b"fake-image-bytes").decode("ascii"),
        )
        body = main.ChatRequest(
            messages=[main.Message(role="user", content="اشرح الصورة")],
            attachments=[attachment],
        )
        with patch.object(main, "API_KEY", "test-api-key"):
            with patch.object(main, "BASE_URL", "https://provider.example/v1"):
                with patch.object(main, "MODEL", "meta/llama-text-only"):
                    with patch.dict(os.environ, {"AI_VISION_MODEL": ""}):
                        with self.assertRaises(HTTPException) as caught:
                            await main.chat(body)
        self.assertEqual(caught.exception.status_code, 503)

    async def test_search_context_is_attached_and_sources_are_returned(self):
        source = {
            "title": "Official docs",
            "url": "https://example.com/docs",
            "content": "The documented behavior",
            "published_date": "2026-11-19",
        }
        search = AsyncMock(return_value=[source])
        body = main.ChatRequest(messages=[
            main.Message(role="user", content="ابحث على النت عن التوثيق الرسمي")
        ])
        with patch.object(main, "API_KEY", "test-api-key"):
            with patch.object(main, "_live_web_search", search):
                with patch("backend.app.main.httpx.AsyncClient", FakeProviderClient):
                    result = await main.chat(body)
        search.assert_awaited_once()
        self.assertIn("https://example.com/docs", str(FakeProviderClient.payloads[-1]["messages"]))
        self.assertEqual(result["sources"][0]["url"], "https://example.com/docs")

    def test_chat_validation_errors_are_actionable_and_do_not_echo_input(self):
        detail = main._validation_detail("/api/chat", [{
            "loc": ("body", "messages", 0, "content"),
            "type": "string_too_long",
            "input": "PRIVATE USER MESSAGE",
        }])
        self.assertIn("100,000 characters", detail)
        self.assertNotIn("PRIVATE USER MESSAGE", detail)

    def test_chat_validation_empty_message_has_clear_feedback(self):
        detail = main._validation_detail("/api/chat", [{
            "loc": ("body", "messages", 0, "content"),
            "type": "string_too_short",
        }])
        self.assertIn("empty", detail.lower())

    def test_other_validation_errors_do_not_expose_submitted_data(self):
        detail = main._validation_detail("/api/auth/login", [{
            "loc": ("body", "password"),
            "type": "string_too_short",
            "input": "secret-password",
        }])
        self.assertEqual(detail, "Invalid request data.")
        self.assertNotIn("secret-password", detail)

    async def test_normal_question_does_not_trigger_live_search(self):
        search = AsyncMock(return_value=[])
        body = main.ChatRequest(messages=[
            main.Message(role="user", content="اشرحلي يعني إيه متغير في البرمجة")
        ])
        with patch.object(main, "API_KEY", "test-api-key"):
            with patch.object(main, "_live_web_search", search):
                with patch("backend.app.main.httpx.AsyncClient", FakeProviderClient):
                    await main.chat(body)
        search.assert_not_awaited()


class LegacyConversationContextRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_filters_unrelated_legacy_context_before_provider_inference(self):
        body = main.ChatRequest(
            messages=[main.Message(role="user", content="صلح HAMASA FastAPI backend")],
            memory=(
                "سياق أقدم من المحادثة الحالية:\\n"
                "المستخدم: ZEGO Disk Health OS uses Debian live-build.\\n"
                "المستخدم: HAMASA AI backend uses FastAPI and Railway."
            ),
        )
        with patch.object(main, "API_KEY", "test-api-key"):
            with patch("backend.app.main.httpx.AsyncClient", FakeProviderClient):
                await main.chat(body)

        provider_context = str(FakeProviderClient.payloads[-1]["messages"])
        self.assertIn("HAMASA AI backend uses FastAPI and Railway", provider_context)
        self.assertNotIn("ZEGO Disk Health OS", provider_context)


if __name__ == "__main__":
    unittest.main()
