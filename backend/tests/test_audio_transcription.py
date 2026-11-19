import base64
import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend.app import main


class FakeGeminiResponse:
    status_code = 200
    text = ""
    def json(self):
        return {"candidates": [{
            "content": {"parts": [{"text": "عامل إيه يا حماصة؟"}]}
        }]}


class FakeGeminiClient:
    calls = []
    def __init__(self, **kwargs):
        pass
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        return False
    async def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return FakeGeminiResponse()


class AudioTranscriptionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        FakeGeminiClient.calls = []

    async def test_transcription_uses_server_key_and_returns_transcript(self):
        body = main.TranscriptionRequest(
            audio=base64.b64encode(bytes(range(256)) * 6).decode("ascii"),
            mime_type="audio/mp4",
        )
        with patch.dict(os.environ, {"TTS_GEMINI_API_KEY": "private-test-key"}):
            with patch("backend.app.main.httpx.AsyncClient", FakeGeminiClient):
                result = await main.transcribe_audio(body)
        self.assertEqual(result["transcript"], "عامل إيه يا حماصة؟")
        call = FakeGeminiClient.calls[0]
        self.assertNotIn("private-test-key", call["url"])
        self.assertEqual(call["headers"]["x-goog-api-key"], "private-test-key")
        self.assertEqual(call["json"]["generationConfig"]["temperature"], 0)

    async def test_transcription_rejects_invalid_base64(self):
        body = main.TranscriptionRequest(audio="not-base64!", mime_type="audio/mp4")
        with patch.dict(os.environ, {"TTS_GEMINI_API_KEY": "private-test-key"}):
            with self.assertRaises(HTTPException) as caught:
                await main.transcribe_audio(body)
        self.assertEqual(caught.exception.status_code, 400)

    async def test_transcription_rejects_too_short_recordings(self):
        body = main.TranscriptionRequest(audio=base64.b64encode(b"short").decode("ascii"))
        with patch.dict(os.environ, {"TTS_GEMINI_API_KEY": "private-test-key"}):
            with self.assertRaises(HTTPException) as caught:
                await main.transcribe_audio(body)
        self.assertEqual(caught.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
