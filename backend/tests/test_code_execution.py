import os
import unittest
from unittest.mock import patch

from backend.app import agent_tools


class FakeHealthResponse:
    status_code = 200

    def json(self):
        return {"status": "ok", "configured": True}


class FakeResponse:
    status_code = 200

    def json(self):
        return {
            "ok": True,
            "language": "python",
            "exit_code": 0,
            "stdout": "2\n",
            "stderr": "",
            "timed_out": False,
            "truncated": False,
            "duration_ms": 18,
        }


class FakeAsyncClient:
    calls = []

    def __init__(self, **kwargs):
        self.options = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, headers=None):
        self.calls.append({"method": "GET", "url": url, "headers": headers, "options": self.options})
        return FakeHealthResponse()

    async def post(self, url, headers=None, json=None):
        self.calls.append({
            "method": "POST",
            "url": url,
            "headers": headers,
            "json": json,
            "options": self.options,
        })
        return FakeResponse()


class IsolatedCodeExecutionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        FakeAsyncClient.calls = []

    def test_runner_is_disabled_without_all_three_settings(self):
        cases = [
            {},
            {"HAMASA_EXECUTOR_ENABLED": "true"},
            {"HAMASA_EXECUTOR_ENABLED": "true", "HAMASA_EXECUTOR_URL": "http://runner:3000"},
            {"HAMASA_EXECUTOR_URL": "http://runner:3000", "HAMASA_EXECUTOR_TOKEN": "secret"},
        ]
        for values in cases:
            with self.subTest(values=values):
                with patch.dict(os.environ, values, clear=True):
                    self.assertFalse(agent_tools.code_execution_available())

    def test_runner_is_enabled_only_with_explicit_flag_url_and_token(self):
        with patch.dict(os.environ, {
            "HAMASA_EXECUTOR_ENABLED": "true",
            "HAMASA_EXECUTOR_URL": "http://hamasa-code-sandbox.railway.internal:3000",
            "HAMASA_EXECUTOR_TOKEN": "shared-secret",
        }, clear=True):
            self.assertTrue(agent_tools.code_execution_available())

    def test_run_code_tool_is_not_advertised_until_runner_is_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertNotIn("run_code", [
                item["function"]["name"] for item in agent_tools.get_chat_tools()
            ])
        with patch.dict(os.environ, {
            "HAMASA_EXECUTOR_ENABLED": "true",
            "HAMASA_EXECUTOR_URL": "http://runner:3000",
            "HAMASA_EXECUTOR_TOKEN": "shared-secret",
        }, clear=True):
            self.assertIn("run_code", [
                item["function"]["name"] for item in agent_tools.get_chat_tools()
            ])

    def test_code_request_rejects_unsupported_or_oversized_input(self):
        with self.assertRaises(ValueError):
            agent_tools.validate_code_request("bash", "echo hello")
        with self.assertRaises(ValueError):
            agent_tools.validate_code_request("python", " ")
        with self.assertRaises(ValueError):
            agent_tools.validate_code_request("javascript", "x" * 50_001)
        self.assertEqual(
            agent_tools.validate_code_request("python", "print(1 + 1)"),
            ("python", "print(1 + 1)"),
        )

    async def test_source_is_forwarded_to_private_runner_without_extra_credentials(self):
        with patch.dict(os.environ, {
            "HAMASA_EXECUTOR_ENABLED": "true",
            "HAMASA_EXECUTOR_URL": "http://hamasa-code-sandbox.railway.internal:3000/",
            "HAMASA_EXECUTOR_TOKEN": "shared-secret",
            "API_KEY": "must-not-be-forwarded",
            "DATABASE_URL": "postgresql://must-not-be-forwarded",
        }, clear=True):
            with patch.object(agent_tools.httpx, "AsyncClient", FakeAsyncClient):
                result = await agent_tools.run_isolated_code("python", "print(1 + 1)")

        self.assertTrue(result["ok"])
        self.assertEqual(result["stdout"], "2\n")
        health_call, call = FakeAsyncClient.calls
        self.assertEqual(health_call["method"], "GET")
        self.assertEqual(health_call["url"], "http://hamasa-code-sandbox.railway.internal:3000/health")
        self.assertEqual(call["method"], "POST")
        self.assertEqual(call["url"], "http://hamasa-code-sandbox.railway.internal:3000/execute")
        self.assertEqual(call["json"], {"language": "python", "code": "print(1 + 1)"})
        self.assertEqual(call["headers"]["Authorization"], "Bearer shared-secret")
        self.assertNotIn("must-not-be-forwarded", str(call["json"]))
        self.assertNotIn("DATABASE_URL", str(call["json"]))
        self.assertFalse(call["options"]["follow_redirects"])
        self.assertFalse(call["options"]["trust_env"])
        self.assertEqual(call["options"]["timeout"].read, 300.0)
        self.assertEqual(call["options"]["timeout"].connect, 8.0)

    async def test_success_response_with_invalid_json_is_rejected(self):
        class InvalidResponse:
            status_code = 200

            def json(self):
                raise ValueError("not json")

        class InvalidJsonClient(FakeAsyncClient):
            async def post(self, url, headers=None, json=None):
                return InvalidResponse()

        with patch.dict(os.environ, {
            "HAMASA_EXECUTOR_ENABLED": "true",
            "HAMASA_EXECUTOR_URL": "http://runner:3000",
            "HAMASA_EXECUTOR_TOKEN": "shared-secret",
        }, clear=True):
            with patch.object(agent_tools.httpx, "AsyncClient", InvalidJsonClient):
                result = await agent_tools.run_isolated_code("javascript", "console.log(1)")

        self.assertFalse(result["ok"])
        self.assertIn("invalid response", result["error"].lower())

    async def test_runner_health_must_report_configured_before_code_is_sent(self):
        class NotReadyResponse:
            status_code = 200

            def json(self):
                return {"status": "ok", "configured": False}

        class NotReadyClient(FakeAsyncClient):
            async def get(self, url, headers=None):
                self.calls.append({"method": "GET", "url": url})
                return NotReadyResponse()

            async def post(self, url, headers=None, json=None):
                self.calls.append({"method": "POST", "url": url, "json": json})
                raise AssertionError("code must not be sent to an unconfigured runner")

        with patch.dict(os.environ, {
            "HAMASA_EXECUTOR_ENABLED": "true",
            "HAMASA_EXECUTOR_URL": "http://runner:3000",
            "HAMASA_EXECUTOR_TOKEN": "shared-secret",
        }, clear=True):
            with patch.object(agent_tools.httpx, "AsyncClient", NotReadyClient):
                result = await agent_tools.run_isolated_code("python", "print('no')")

        self.assertFalse(result["ok"])
        self.assertFalse(result["available"])
        self.assertEqual(len(NotReadyClient.calls), 1)
        self.assertEqual(NotReadyClient.calls[0]["method"], "GET")

    async def test_unconfigured_runner_never_attempts_execution(self):
        with patch.dict(os.environ, {}, clear=True):
            result = await agent_tools.run_isolated_code("javascript", "console.log(1)")
        self.assertFalse(result["ok"])
        self.assertFalse(result["available"])
        self.assertEqual(FakeAsyncClient.calls, [])


if __name__ == "__main__":
    unittest.main()
