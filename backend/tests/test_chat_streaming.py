import json
import unittest
from unittest.mock import patch

from backend.app import main


class FakeStreamResponse:
    status_code = 200
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        return False
    async def aread(self):
        return b""
    async def aiter_lines(self):
        yield "data: " + json.dumps({"choices": [{"delta": {"content": "Hello "}}]})
        yield "data: " + json.dumps({"choices": [{"delta": {"content": "world"}}]})
        yield "data: [DONE]"


class FakeStreamingClient:
    def __init__(self, **kwargs):
        self.options = kwargs
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        return False
    def stream(self, method, url, headers=None, json=None):
        return FakeStreamResponse()


class ChatStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_stream_returns_incremental_events_and_done_marker(self):
        body = main.ChatRequest(messages=[main.Message(role="user", content="Hello")])
        with patch.object(main, "API_KEY", "test-key"):
            with patch("backend.app.main.httpx.AsyncClient", FakeStreamingClient):
                response = await main.chat_stream(body)
                chunks = []
                async for chunk in response.body_iterator:
                    chunks.append(chunk.decode() if isinstance(chunk, bytes) else str(chunk))
        output = "".join(chunks)
        self.assertEqual(response.media_type, "text/event-stream")
        self.assertIn('"type": "delta"', output)
        self.assertIn("Hello ", output)
        self.assertIn("world", output)
        self.assertIn('"type": "done"', output)


if __name__ == "__main__":
    unittest.main()
