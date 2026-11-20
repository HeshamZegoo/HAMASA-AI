import base64
import unittest
from unittest.mock import AsyncMock, patch

from backend.app.github_tools import read_public_github_file, validate_github_file_request
from backend.app.agent_tools import execute_chat_tool


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeClient:
    def __init__(self, response):
        self.response = response
        self.requested_url = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url):
        self.requested_url = url
        return self.response


class PublicGitHubReaderValidationTests(unittest.TestCase):
    def test_accepts_public_repo_file(self):
        self.assertEqual(
            validate_github_file_request("octocat", "hello-world", "README.md", "main"),
            ("octocat", "hello-world", "README.md", "main"),
        )

    def test_rejects_path_traversal(self):
        with self.assertRaises(ValueError):
            validate_github_file_request("octocat", "hello-world", "../secrets.txt")

    def test_rejects_backslash_path(self):
        with self.assertRaises(ValueError):
            validate_github_file_request("octocat", "hello-world", "src\\..\\secret")

    def test_rejects_invalid_ref(self):
        with self.assertRaises(ValueError):
            validate_github_file_request("octocat", "hello-world", "README.md", "../../main")

    def test_rejects_url_as_owner(self):
        with self.assertRaises(ValueError):
            validate_github_file_request("https://evil.example", "repo", "README.md")


class PublicGitHubReaderRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_reads_and_decodes_utf8_file(self):
        encoded = base64.b64encode("Hello HAMASA — أهلاً".encode("utf-8")).decode("ascii")
        client = _FakeClient(_FakeResponse({
            "type": "file",
            "size": len(base64.b64decode(encoded)),
            "encoding": "base64",
            "content": encoded,
            "html_url": "https://github.com/octocat/hello-world/blob/main/README.md",
        }))
        with patch("backend.app.github_tools.httpx.AsyncClient", return_value=client):
            result = await read_public_github_file("octocat", "hello-world", "README.md", "main")

        self.assertTrue(result["ok"])
        self.assertEqual(result["content"], "Hello HAMASA — أهلاً")
        self.assertEqual(result["repository"], "octocat/hello-world")
        self.assertEqual(result["path"], "README.md")
        self.assertIn("/repos/octocat/hello-world/contents/README.md", client.requested_url)

    async def test_rejects_directory_response(self):
        client = _FakeClient(_FakeResponse({"type": "dir", "size": 0}))
        with patch("backend.app.github_tools.httpx.AsyncClient", return_value=client):
            with self.assertRaisesRegex(ValueError, "not a single file"):
                await read_public_github_file("octocat", "hello-world", "docs", "main")

    async def test_rejects_file_over_size_limit_before_decoding(self):
        client = _FakeClient(_FakeResponse({
            "type": "file", "size": 65537, "encoding": "base64", "content": "",
        }))
        with patch("backend.app.github_tools.httpx.AsyncClient", return_value=client):
            with self.assertRaisesRegex(ValueError, "64 KiB"):
                await read_public_github_file("octocat", "hello-world", "large.txt", "main")

    async def test_rejects_non_utf8_file(self):
        encoded = base64.b64encode(b"\\xff\\xfe").decode("ascii")
        client = _FakeClient(_FakeResponse({
            "type": "file", "size": 2, "encoding": "base64", "content": encoded,
        }))
        with patch("backend.app.github_tools.httpx.AsyncClient", return_value=client):
            with self.assertRaisesRegex(ValueError, "valid UTF-8"):
                await read_public_github_file("octocat", "hello-world", "binary.txt", "main")

    async def test_dispatcher_routes_github_read_tool(self):
        expected = {"ok": True, "content": "from mocked GitHub"}
        search = AsyncMock(return_value=[])
        with patch("backend.app.agent_tools.read_public_github_file", new=AsyncMock(return_value=expected)) as reader:
            result = await execute_chat_tool(
                "github_read_file",
                {"owner": "octocat", "repo": "hello-world", "path": "README.md"},
                search,
            )
        self.assertEqual(result, expected)
        reader.assert_awaited_once_with("octocat", "hello-world", "README.md", "HEAD")


if __name__ == "__main__":
    unittest.main()
