import base64
import os
import unittest
from unittest.mock import patch, AsyncMock

from fastapi import HTTPException

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


class FakeToolCallResponse:
    status_code = 200
    def __init__(self, message):
        self.message = message
    def json(self):
        return {"choices": [{"message": self.message}]}


class FakeToolCallingClient:
    payloads = []
    def __init__(self, **kwargs):
        pass
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        return False
    async def post(self, url, headers=None, json=None):
        self.payloads.append(json)
        if len(self.payloads) == 1:
            return FakeToolCallResponse({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_calc_1",
                    "type": "function",
                    "function": {"name": "calculator", "arguments": "{\\"expression\\":\\"12 * 13\\"}"},
                }],
            })
        return FakeToolCallResponse({"role": "assistant", "content": "12 × 13 = 156"})


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

    async def test_model_can_call_calculator_and_receive_real_result(self):
        FakeToolCallingClient.payloads = []
        body = main.ChatRequest(messages=[
            main.Message(role="user", content="احسب 12 في 13")
        ])
        with patch.object(main, "API_KEY", "test-api-key"):
            with patch("backend.app.main.httpx.AsyncClient", FakeToolCallingClient):
                result = await main.chat(body)
        self.assertEqual(result["reply"], "12 × 13 = 156")
        self.assertEqual(len(FakeToolCallingClient.payloads), 2)
        tool_message = FakeToolCallingClient.payloads[1]["messages"][-1]
        self.assertEqual(tool_message["role"], "tool")
        self.assertEqual(tool_message["tool_call_id"], "call_calc_1")
        self.assertIn('"result": 156', tool_message["content"])


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


if __name__ == "__main__":
    unittest.main()
