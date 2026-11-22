import asyncio
import base64
import os
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from backend.app.main import TranscriptionRequest, transcribe_audio


class NvidiaTranscriptionTests(unittest.TestCase):
    def _run(self, coroutine):
        return asyncio.run(coroutine)

    def _fake_client(self, statuses):
        class FakeResponse:
            def __init__(self, status_code, headers=None):
                self.status_code = status_code
                self.headers = headers or {}
                self.text = "provider response"

            def json(self):
                return {"text": "أهلاً، hello"}

        class FakeClient:
            calls = 0

            def __init__(self, **kwargs):
                self.responses = [
                    FakeResponse(*status) if isinstance(status, tuple) else FakeResponse(status)
                    for status in statuses
                ]

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, headers=None, data=None, files=None):
                type(self).calls += 1
                return self.responses.pop(0)

        return FakeClient

    def test_transcription_uses_shared_nvidia_key_and_whisper_endpoint(self):
        audio = b"\x01" * 2048

        class FakeResponse:
            status_code = 200
            text = ""
            def json(self):
                return {"text": "أهلاً، hello"}

        class FakeClient:
            calls = []
            def __init__(self, **kwargs):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, exc_type, exc, tb):
                return False
            async def post(self, url, headers=None, data=None, files=None):
                self.calls.append((url, headers, data, files))
                return FakeResponse()

        with patch.dict(os.environ, {"AI_API_KEY": "shared-nvidia-key"}):
            with patch("backend.app.main.httpx.AsyncClient", FakeClient):
                result = self._run(transcribe_audio(TranscriptionRequest(
                    audio=base64.b64encode(audio).decode("ascii"),
                    mime_type="audio/wav",
                )))

        self.assertEqual(result["transcript"], "أهلاً، hello")
        url, headers, data, files = FakeClient.calls[0]
        self.assertIn("b702f636-f60c-4a3d-a6f4-f3568c13bd7d", url)
        self.assertTrue(url.endswith("/v1/audio/transcriptions"))
        self.assertEqual(headers["Authorization"], "Bearer shared-nvidia-key")
        self.assertEqual(data["language"], "multi")
        self.assertEqual(files["file"][1], audio)

    def test_transcription_requires_the_same_provider_key(self):
        with patch.dict(os.environ, {"AI_API_KEY": ""}):
            with patch("backend.app.main.API_KEY", ""):
                with self.assertRaises(HTTPException) as raised:
                    self._run(transcribe_audio(TranscriptionRequest(
                        audio=base64.b64encode(b"x" * 2048).decode("ascii"),
                        mime_type="audio/wav",
                    )))
        self.assertEqual(raised.exception.status_code, 503)

    def test_transcription_recovers_after_transient_provider_5xx_responses(self):
        audio = b"x" * 2048
        fake_client = self._fake_client([500, 503, 200])

        with patch.dict(os.environ, {"AI_API_KEY": "shared-nvidia-key"}):
            with patch("backend.app.main.httpx.AsyncClient", fake_client):
                with patch("backend.app.main.asyncio.sleep", new_callable=AsyncMock) as sleep:
                    result = self._run(transcribe_audio(TranscriptionRequest(
                        audio=base64.b64encode(audio).decode("ascii"),
                        mime_type="audio/wav",
                    )))

        self.assertEqual(result["transcript"], "أهلاً، hello")
        self.assertEqual(fake_client.calls, 3)
        self.assertEqual(
            [call.args[0] for call in sleep.await_args_list],
            [1.0, 2.0],
        )

    def test_transcription_retries_rate_limit_using_retry_after_header(self):
        audio = b"x" * 2048
        fake_client = self._fake_client([(429, {"Retry-After": "1"}), 200])

        with patch.dict(os.environ, {"AI_API_KEY": "shared-nvidia-key"}):
            with patch("backend.app.main.httpx.AsyncClient", fake_client):
                with patch("backend.app.main.asyncio.sleep", new_callable=AsyncMock) as sleep:
                    result = self._run(transcribe_audio(TranscriptionRequest(
                        audio=base64.b64encode(audio).decode("ascii"),
                        mime_type="audio/wav",
                    )))

        self.assertEqual(result["transcript"], "أهلاً، hello")
        self.assertEqual(fake_client.calls, 2)
        sleep.assert_awaited_once_with(1.0)

    def test_transcription_returns_502_after_three_provider_5xx_attempts(self):
        audio = b"x" * 2048
        fake_client = self._fake_client([500, 500, 500])

        with patch.dict(os.environ, {"AI_API_KEY": "shared-nvidia-key"}):
            with patch("backend.app.main.httpx.AsyncClient", fake_client):
                with patch("backend.app.main.asyncio.sleep", new_callable=AsyncMock) as sleep:
                    with self.assertRaises(HTTPException) as raised:
                        self._run(transcribe_audio(TranscriptionRequest(
                            audio=base64.b64encode(audio).decode("ascii"),
                            mime_type="audio/wav",
                        )))

        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(fake_client.calls, 3)
        self.assertEqual(sleep.await_count, 2)

    def test_transcription_does_not_retry_non_rate_limit_4xx_responses(self):
        audio = b"x" * 2048
        fake_client = self._fake_client([400])

        with patch.dict(os.environ, {"AI_API_KEY": "shared-nvidia-key"}):
            with patch("backend.app.main.httpx.AsyncClient", fake_client):
                with patch("backend.app.main.asyncio.sleep", new_callable=AsyncMock) as sleep:
                    with self.assertRaises(HTTPException) as raised:
                        self._run(transcribe_audio(TranscriptionRequest(
                            audio=base64.b64encode(audio).decode("ascii"),
                            mime_type="audio/wav",
                        )))

        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(fake_client.calls, 1)
        sleep.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
