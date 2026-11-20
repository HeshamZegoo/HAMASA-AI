import unittest
from unittest.mock import patch

from backend.app.agent_tools import (
    calculate,
    code_execution_available,
    get_chat_tools,
    validate_code_request,
    run_isolated_code,
)


class CalculatorToolTests(unittest.TestCase):
    def test_basic_arithmetic(self):
        self.assertEqual(calculate("(1250 * 3) - 500")["result"], 3250)

    def test_division(self):
        self.assertEqual(calculate("10 / 4")["result"], 2.5)

    def test_rejects_python_execution(self):
        with self.assertRaises((ValueError, TypeError)):
            calculate("__import__('os').getcwd()")

    def test_rejects_names_and_attributes(self):
        with self.assertRaises((ValueError, TypeError)):
            calculate("open('/etc/passwd')")

    def test_rejects_extreme_exponents(self):
        with self.assertRaises(ValueError):
            calculate("2 ** 101")

    def test_code_execution_is_disabled_without_private_runner_configuration(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(code_execution_available())
            self.assertNotIn("run_code", [tool["function"]["name"] for tool in get_chat_tools()])

    def test_code_execution_tool_is_exposed_only_when_enabled_and_authenticated(self):
        with patch.dict("os.environ", {
            "HAMASA_EXECUTOR_ENABLED": "true",
            "HAMASA_EXECUTOR_URL": "http://hamasa-code-sandbox.railway.internal:3000",
            "HAMASA_EXECUTOR_TOKEN": "test-token",
        }, clear=True):
            self.assertTrue(code_execution_available())
            self.assertIn("run_code", [tool["function"]["name"] for tool in get_chat_tools()])

    def test_code_request_accepts_python_and_javascript_only(self):
        self.assertEqual(validate_code_request("python", "print(1)"), ("python", "print(1)"))
        self.assertEqual(validate_code_request("javascript", "console.log(1)")[0], "javascript")
        with self.assertRaises(ValueError):
            validate_code_request("bash", "whoami")

    def test_code_request_rejects_empty_or_oversized_source(self):
        with self.assertRaises(ValueError):
            validate_code_request("python", "  ")
        with self.assertRaises(ValueError):
            validate_code_request("python", "x" * 50_001)


class IsolatedCodeRunnerClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_forwards_code_only_to_private_executor_with_bearer_auth(self):
        captured = {}

        class FakeHealthResponse:
            status_code = 200
            def json(self):
                return {"status": "ok", "configured": True}

        class FakeResponse:
            status_code = 200
            def json(self):
                return {"ok": True, "language": "python", "stdout": "2\\n", "stderr": "", "exit_code": 0}

        class FakeClient:
            def __init__(self, **kwargs):
                captured["client_options"] = kwargs
            async def __aenter__(self):
                return self
            async def __aexit__(self, exc_type, exc, tb):
                return False
            async def get(self, url, headers=None):
                captured["health_url"] = url
                return FakeHealthResponse()
            async def post(self, url, headers=None, json=None):
                captured.update({"url": url, "headers": headers, "json": json})
                return FakeResponse()

        with patch.dict("os.environ", {
            "HAMASA_EXECUTOR_ENABLED": "true",
            "HAMASA_EXECUTOR_URL": "http://hamasa-code-sandbox.railway.internal:3000/",
            "HAMASA_EXECUTOR_TOKEN": "private-test-token",
        }, clear=True):
            with patch("backend.app.agent_tools.httpx.AsyncClient", FakeClient):
                result = await run_isolated_code("python", "print(1 + 1)")

        self.assertTrue(result["ok"])
        self.assertEqual(captured["health_url"], "http://hamasa-code-sandbox.railway.internal:3000/health")
        self.assertEqual(captured["url"], "http://hamasa-code-sandbox.railway.internal:3000/execute")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer private-test-token")
        self.assertEqual(captured["json"], {"language": "python", "code": "print(1 + 1)"})
        self.assertNotIn("private-test-token", str(captured["json"]))



if __name__ == "__main__":
    unittest.main()
