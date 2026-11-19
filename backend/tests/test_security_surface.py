import os
import asyncio
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from fastapi import Request, Response
from cryptography.fernet import Fernet

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
                            "AI_API_KEY": "transcription-key",
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

    def test_memory_and_account_capabilities_validate_key_formats(self):
        with patch.object(main, "DATABASE_URL", "postgresql://db.example/test"):
            with patch.object(main, "MEMORY_ENCRYPTION_KEY", "not-a-fernet-key"):
                with patch.object(main, "JWT_SECRET", "too-short"):
                    unavailable = main._runtime_tool_status()
            with patch.object(main, "MEMORY_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii")):
                with patch.object(main, "JWT_SECRET", "j" * 40):
                    available = main._runtime_tool_status()
        self.assertFalse(unavailable["memory"])
        self.assertFalse(unavailable["accounts"])
        self.assertTrue(available["memory"])
        self.assertTrue(available["accounts"])

    def test_shared_chat_provider_key_also_enables_nvidia_speech(self):
        with patch.object(main, "API_KEY", "shared-provider-key"):
            with patch.dict(os.environ, {"AI_API_KEY": ""}):
                with patch.object(main, "BASE_URL", "https://api.openai.com/v1"):
                    self.assertTrue(main._runtime_tool_status()["speech"])

    def test_speech_is_unavailable_when_shared_provider_key_is_missing(self):
        with patch.object(main, "API_KEY", ""):
            with patch.dict(os.environ, {"AI_API_KEY": ""}):
                self.assertFalse(main._runtime_tool_status()["speech"])

    def test_sqlite_does_not_claim_cloud_persistent_memory_or_accounts(self):
        with patch.object(main, "JWT_SECRET", "j" * 40):
            with patch.object(main, "MEMORY_ENCRYPTION_KEY", "fernet-key"):
                with patch.object(main, "DATABASE_URL", "sqlite:////tmp/hamasa.db"):
                    status = main._runtime_tool_status()
        self.assertFalse(status["memory"])
        self.assertFalse(status["accounts"])

    def test_rate_limit_state_prunes_expired_client_buckets(self):
        main._rate_events.clear()
        expired = ("192.0.2.10", "/api/chat", "POST")
        active = ("192.0.2.11", "/api/chat", "POST")
        main._rate_events[expired].append(0.0)
        main._rate_events[active].append(999.0)
        main._prune_rate_events(1000.0)
        self.assertNotIn(expired, main._rate_events)
        self.assertIn(active, main._rate_events)
        main._rate_events.clear()

    def test_rate_limit_state_is_capped_under_high_cardinality(self):
        main._rate_events.clear()
        for index in range(25001):
            main._rate_events[(f"198.51.100.{index}", "/api/chat", "POST")].append(999.0)
        main._prune_rate_events(1000.0)
        self.assertLessEqual(len(main._rate_events), 25000)
        main._rate_events.clear()

    def test_oversized_chat_and_audio_bodies_are_rejected_before_parsing(self):
        async def invoke(path, content_length):
            scope = {
                "type": "http",
                "asgi": {"version": "3.0", "spec_version": "2.3"},
                "http_version": "1.1",
                "method": "POST",
                "scheme": "https",
                "path": path,
                "raw_path": path.encode("ascii"),
                "query_string": b"",
                "headers": [
                    (b"host", b"testserver"),
                    (b"content-length", str(content_length).encode("ascii")),
                ],
                "client": ("192.0.2.250", 12345),
                "server": ("testserver", 443),
            }
            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}
            async def call_next(_request):
                return Response("ok")
            return await main.security_and_rate_limit(Request(scope, receive), call_next)

        chat = asyncio.run(invoke("/api/chat", 91 * 1024 * 1024))
        audio = asyncio.run(invoke("/api/transcribe", 18 * 1024 * 1024))
        self.assertEqual(chat.status_code, 413)
        self.assertEqual(audio.status_code, 413)

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
        with patch.dict(os.environ, {"AI_API_KEY": "private-audio-secret"}):
            response = self.client.get("/api/tts/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertNotIn("private-audio-secret", response.text)


if __name__ == "__main__":
    unittest.main()
