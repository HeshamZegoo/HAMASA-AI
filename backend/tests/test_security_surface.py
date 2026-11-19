import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import main


class PublicStatusDisclosureTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_root_exposes_only_liveness(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "online"})

    def test_health_does_not_disclose_provider_or_model_configuration(self):
        with patch.object(main, "MODEL", "private-internal-model"):
            with patch.dict(os.environ, {"TAVILY_API_KEY": "private-search-secret"}):
                response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertNotIn("private-internal-model", response.text)
        self.assertNotIn("private-search-secret", response.text)

    def test_tts_status_does_not_disclose_provider_configuration(self):
        with patch.dict(os.environ, {"TTS_GEMINI_API_KEY": "private-audio-secret"}):
            response = self.client.get("/api/tts/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertNotIn("private-audio-secret", response.text)


if __name__ == "__main__":
    unittest.main()
