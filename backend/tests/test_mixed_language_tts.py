import base64
import io
import unittest
import wave
from unittest.mock import patch
import os

from backend.app.main import TTSRequest, _pcm_silence, _tts_segments, text_to_speech


class MixedLanguageTTSTests(unittest.TestCase):
    def test_mixed_arabic_and_english_switches_locale_in_order(self):
        segments = _tts_segments("أهلاً، welcome to HAMASA! عامل إيه؟")
        self.assertEqual(
            [language for _, language in segments],
            ["ar-XA", "en-US", "ar-XA"],
        )
        self.assertEqual("".join(text for text, _ in segments), "أهلاً، welcome to HAMASA! عامل إيه؟")

    async def _fake_wav(self):
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(22050)
            wav.writeframes(bytes([1, 0]) * 100)
        return output.getvalue()

    def test_tts_endpoint_synthesizes_each_language_in_order_and_merges_wav(self):
        class FakeResponse:
            status_code = 200
            text = ""
            def __init__(self, content):
                self.content = content

        audio = self._run_async(self._fake_wav())

        class FakeClient:
            calls = []
            def __init__(self, **kwargs):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, exc_type, exc, tb):
                return False
            async def post(self, url, headers=None, data=None):
                self.calls.append(data.copy())
                return FakeResponse(audio)

        with patch.dict(os.environ, {"AI_API_KEY": "test-provider-key"}):
            with patch("backend.app.main.httpx.AsyncClient", FakeClient):
                result = self._run_async(text_to_speech(
                    TTSRequest(text="أهلاً welcome عامل إيه", gender="female")
                ))

        self.assertEqual([call["language"] for call in FakeClient.calls], ["ar-XA", "en-US", "ar-XA"])
        self.assertTrue(all(call["voice"].endswith(".Sofia") for call in FakeClient.calls))
        decoded = base64.b64decode(result["audio"])
        with wave.open(io.BytesIO(decoded), "rb") as wav:
            self.assertEqual(wav.getnchannels(), 1)
            self.assertEqual(wav.getframerate(), 22050)
            expected_frames = 3 * 100 + 2 * int(22050 * 0.12)
            self.assertEqual(wav.getnframes(), expected_frames)

    @staticmethod
    def _run_async(coro):
        import asyncio
        return asyncio.run(coro)

    def test_pcm_silence_uses_zero_bytes_and_correct_frame_length(self):
        silence = _pcm_silence(nchannels=2, sampwidth=2, framerate=22050, seconds=0.12)
        self.assertEqual(len(silence), int(22050 * 0.12) * 2 * 2)
        self.assertEqual(silence, bytes(len(silence)))

    def test_arabic_only_uses_arabic_locale(self):
        self.assertEqual(_tts_segments("عامل إيه يا صاحبي؟"), [("عامل إيه يا صاحبي؟", "ar-XA")])

    def test_english_only_uses_english_locale(self):
        self.assertEqual(_tts_segments("Hello, how are you?"), [("Hello, how are you?", "en-US")])


if __name__ == "__main__":
    unittest.main()
