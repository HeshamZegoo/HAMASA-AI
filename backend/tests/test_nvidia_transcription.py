import asyncio
import base64
import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend.app.main import TranscriptionRequest, transcribe_audio


class NvidiaTranscriptionTests(unittest.TestCase):
    def _run(self, coroutine):
        return asyncio.run(coroutine)

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


if __name__ == "__main__":
    unittest.main()
