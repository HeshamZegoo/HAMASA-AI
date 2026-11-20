import json
import unittest
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from backend.app import main


class FakeProviderResponse:
    status_code = 200

    def __init__(self, message):
        self.message = message

    def json(self):
        return {"choices": [{"message": self.message}]}


class FakeProviderClient:
    calls = []
    responses = []

    def __init__(self, **kwargs):
        self.options = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return self.responses.pop(0)


class CodeExecutionChatFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        FakeProviderClient.calls = []
        FakeProviderClient.responses = []

    def _patches(self, execute):
        return [
            patch.object(main, "API_KEY", "test-provider-key"),
            patch.object(main, "code_execution_available", return_value=True),
            patch.object(main, "get_chat_tools", return_value=[{
                "type": "function",
                "function": {"name": "run_code", "parameters": {}},
            }]),
            patch.object(main, "execute_chat_tool", execute),
            patch.object(main, "prepare_messages", return_value=[
                {"role": "user", "content": "print(1 + 1)"}
            ]),
            patch.object(main, "coding_instructions_for", return_value=""),
            patch.object(main, "should_search_web", return_value=False),
            patch.object(main.httpx, "AsyncClient", FakeProviderClient),
        ]

    async def test_explicit_code_execution_uses_one_tool_call_and_one_final_completion(self):
        execute = AsyncMock(return_value={
            "ok": True,
            "language": "python",
            "stdout": "2\n",
            "stderr": "",
            "exit_code": 0,
            "timed_out": False,
        })
        FakeProviderClient.responses = [
            FakeProviderResponse({
                "role": "assistant",
                "tool_calls": [{
                    "id": "call-run-code",
                    "type": "function",
                    "function": {
                        "name": "run_code",
                        "arguments": json.dumps({
                            "language": "python",
                            "code": "print(1 + 1)",
                        }),
                    },
                }],
            }),
            FakeProviderResponse({"role": "assistant", "content": "2"}),
        ]
        with ExitStack() as stack:
            for context in self._patches(execute):
                stack.enter_context(context)
            result = await main.chat(main.ChatRequest(messages=[
                main.Message(role="user", content="print(1 + 1)")
            ]))

        self.assertEqual(result["reply"], "2")
        execute.assert_awaited_once()
        self.assertEqual(len(FakeProviderClient.calls), 2)
        self.assertEqual(
            FakeProviderClient.calls[0]["json"]["tool_choice"]["function"]["name"],
            "run_code",
        )
        final_payload = FakeProviderClient.calls[1]["json"]
        self.assertNotIn("tools", final_payload)
        self.assertNotIn("tool_choice", final_payload)
        self.assertTrue(any(
            message.get("role") == "tool" and '"stdout": "2\\n"' in message.get("content", "")
            for message in final_payload["messages"]
        ))

    async def test_missing_required_tool_call_returns_error_instead_of_guessing(self):
        execute = AsyncMock()
        FakeProviderClient.responses = [
            FakeProviderResponse({"role": "assistant", "content": "The answer is 2."})
        ]
        with ExitStack() as stack:
            for context in self._patches(execute):
                stack.enter_context(context)
            with self.assertRaises(HTTPException) as raised:
                await main.chat(main.ChatRequest(messages=[
                    main.Message(role="user", content="print(1 + 1)")
                ]))

        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn("No code was run", raised.exception.detail)
        execute.assert_not_awaited()
        self.assertEqual(len(FakeProviderClient.calls), 1)


if __name__ == "__main__":
    unittest.main()
