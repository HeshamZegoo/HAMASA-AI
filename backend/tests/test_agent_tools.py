import unittest
from unittest.mock import patch

from backend.app.agent_tools import (
    calculate,
    code_execution_available,
    get_chat_tools,
    validate_code_request,
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


if __name__ == "__main__":
    unittest.main()
