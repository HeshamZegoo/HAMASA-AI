import unittest

from backend.app.main import _pcm_silence, _tts_segments


class MixedLanguageTTSTests(unittest.TestCase):
    def test_mixed_arabic_and_english_switches_locale_in_order(self):
        segments = _tts_segments("أهلاً، welcome to HAMASA! عامل إيه؟")
        self.assertEqual(
            [language for _, language in segments],
            ["ar-XA", "en-US", "ar-XA"],
        )
        self.assertEqual("".join(text for text, _ in segments), "أهلاً، welcome to HAMASA! عامل إيه؟")

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
