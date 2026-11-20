import base64
import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend.app import main


class FakeNvidiaResponse:
    status_code = 200
    text = ""

    def json(self):
        return {"text": "عامل إيه يا حماصة؟ Hello!"}


class FakeNvidiaClient:
    calls = []

    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, headers=None, data=None, files=None):
        self.calls.append({"url": url, "headers": headers, "data": data, "files": files})
        return FakeNvidiaResponse()


class AudioTranscriptionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        FakeNvidiaClient.calls = []

    async def test_transcription_uses_shared_nvidia_key_and_returns_mixed_transcript(self):
        audio_bytes = bytes(range(256)) * 6
        body = main.TranscriptionRequest(
            audio=base64.b64encode(audio_bytes).decode("ascii"),
            mime_type="audio/wav",
        )
        with patch.dict(os.environ, {"AI_API_KEY": "shared-provider-test-key"}):
            with patch("backend.app.main.httpx.AsyncClient", FakeNvidiaClient):
                result = await main.transcribe_audio(body)

        self.assertEqual(result["transcript"], "عامل إيه يا حماصة؟ Hello!")
        call = FakeNvidiaClient.calls[0]
        self.assertIn("b702f636-f60c-4a3d-a6f4-f3568c13bd7d", call["url"])
        self.assertTrue(call["url"].endswith("/v1/audio/transcriptions"))
        self.assertEqual(call["headers"]["Authorization"], "Bearer shared-provider-test-key")
        self.assertEqual(call["data"]["language"], "multi")
        self.assertEqual(call["data"]["response_format"], "json")
        self.assertEqual(call["files"]["file"][1], audio_bytes)
        self.assertEqual(call["files"]["file"][2], "audio/wav")

    async def test_invalid_base64_is_rejected_before_provider_lookup(self):
        body = main.TranscriptionRequest(audio="not-base64!", mime_type="audio/mp4")
        with patch.dict(os.environ, {"AI_API_KEY": ""}):
            with patch("backend.app.main.API_KEY", ""):
                with self.assertRaises(HTTPException) as caught:
                    await main.transcribe_audio(body)
        self.assertEqual(caught.exception.status_code, 400)

    async def test_short_recordings_are_rejected_before_provider_lookup(self):
        body = main.TranscriptionRequest(
            audio=base64.b64encode(b"short").decode("ascii"),
            mime_type="audio/mp4",
        )
        with patch.dict(os.environ, {"AI_API_KEY": ""}):
            with patch("backend.app.main.API_KEY", ""):
                with self.assertRaises(HTTPException) as caught:
                    await main.transcribe_audio(body)
        self.assertEqual(caught.exception.status_code, 400)


    async def test_wav_is_normalized_to_mono_16khz_pcm_before_nvidia_upload(self):
        import io
        import wave
        source = io.BytesIO()
        with wave.open(source, "wb") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(22050)
            wav.writeframes((b"\\x01\\x00\\x02\\x00") * 2205)
        normalized = main._normalize_wav_for_nvidia(source.getvalue())
        with wave.open(io.BytesIO(normalized), "rb") as wav:
            self.assertEqual(wav.getnchannels(), 1)
            self.assertEqual(wav.getsampwidth(), 2)
            self.assertEqual(wav.getframerate(), 16000)
            self.assertEqual(wav.getnframes(), 1600)

    async def test_transcription_rejects_unknown_mime_type(self):
        body = main.TranscriptionRequest(
            audio=base64.b64encode(b"x" * 2048).decode("ascii"),
            mime_type="audio/unknown",
        )
        with patch.dict(os.environ, {"AI_API_KEY": "shared-provider-test-key"}):
            with self.assertRaises(HTTPException) as caught:
                await main.transcribe_audio(body)
        self.assertEqual(caught.exception.status_code, 415)

    async def test_valid_audio_requires_the_shared_provider_key(self):
        body = main.TranscriptionRequest(
            audio=base64.b64encode(b"x" * 2048).decode("ascii"),
            mime_type="audio/wav",
        )
        with patch.dict(os.environ, {"AI_API_KEY": ""}):
            with patch("backend.app.main.API_KEY", ""):
                with self.assertRaises(HTTPException) as caught:
                    await main.transcribe_audio(body)
        self.assertEqual(caught.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
