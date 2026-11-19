import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import main


class PublicStatusDisclosureTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_runtime_capabilities_require_real_backing_configuration(self):
        with patch.object(main, "API_KEY", "provider-key"):
            with patch.object(main, "JWT_SECRET", "j" * 40):
                with patch.object(main, "MEMORY_ENCRYPTION_KEY", "fernet-key"):
                    with patch.object(main, "DATABASE_URL", ""):
                        with patch.dict(os.environ, {
                            "TAVILY_API_KEY": "search-key",
                            "TTS_GEMINI_API_KEY": "transcription-key",
                            "AI_VISION_MODEL": "vision-model",
                        }):
                            status = main._runtime_tool_status()
        self.assertTrue(status["chat"])
        self.assertTrue(status["web_search"])
        self.assertTrue(status["vision"])
        self.assertTrue(status["file_generation"])
        self.assertTrue(status["transcription"])
        self.assertTrue(status["speech"])
        self.assertFalse(status["memory"])
        self.assertFalse(status["accounts"])

    def test_sqlite_does_not_claim_cloud_persistent_memory_or_accounts(self):
        with patch.object(main, "JWT_SECRET", "j" * 40):
            with patch.object(main, "MEMORY_ENCRYPTION_KEY", "fernet-key"):
                with patch.object(main, "DATABASE_URL", "sqlite:////tmp/hamasa.db"):
                    status = main._runtime_tool_status()
        self.assertFalse(status["memory"])
        self.assertFalse(status["accounts"])

    def test_api_rejects_untrusted_origins(self):
        response = self.client.get(
            "/api/tts/status",
            headers={"Origin": "https://untrusted.example"},
        )
        self.assertEqual(response.status_code, 403)

    def test_api_sets_browser_security_headers(self):
        response = self.client.get(
            "/api/tts/status",
            headers={"Origin": "https://heshamzegoo.github.io"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")

    def test_readiness_requires_chat_provider_configuration(self):
        with patch.object(main, "API_KEY", ""):
            unavailable = self.client.get("/ready")
        self.assertEqual(unavailable.status_code, 503)
        self.assertNotIn("API_KEY", unavailable.text)

        with patch.object(main, "API_KEY", "private-provider-key"):
            ready = self.client.get("/ready")
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.json(), {"status": "ready"})
        self.assertNotIn("private-provider-key", ready.text)

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
