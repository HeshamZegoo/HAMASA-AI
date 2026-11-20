import unittest
from unittest.mock import AsyncMock, patch

from backend.app.agent_tools import (
    _ReadableHTML,
    _validate_public_url,
    execute_chat_tool,
)


class WebReaderSafetyTests(unittest.IsolatedAsyncioTestCase):
    def test_html_reader_extracts_text_title_and_links(self):
        parser = _ReadableHTML()
        parser.feed(
            "<html><head><title>Example Page</title>"
            "<script>ignore secret</script></head>"
            "<body><h1>Hello</h1><p>Readable text</p>"
            '<a href="/docs">Documentation</a></body></html>'
        )
        self.assertEqual(" ".join(parser.title_parts), "Example Page")
        text = " ".join(" ".join(parser.parts).split())
        self.assertIn("Hello", text)
        self.assertIn("Readable text", text)
        self.assertNotIn("ignore secret", text)
        self.assertEqual(parser.links[0]["href"], "/docs")

    async def test_blocks_loopback_and_private_addresses(self):
        for url in (
            "http://127.0.0.1/",
            "http://10.0.0.5/",
            "http://192.168.1.1/",
            "http://[::1]/",
            "http://localhost/",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    await _validate_public_url(url)

    async def test_rejects_non_http_schemes_and_credentials(self):
        for url in ("file:///etc/passwd", "ftp://example.com/file", "https://user:pass@example.com"):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    await _validate_public_url(url)

    async def test_open_webpage_tool_routes_to_reader(self):
        with patch("backend.app.agent_tools.open_webpage", new=AsyncMock(return_value={"ok": True, "title": "Example"})) as reader:
            result = await execute_chat_tool("open_webpage", {"url": "https://example.com"}, AsyncMock())
        self.assertTrue(result["ok"])
        reader.assert_awaited_once_with("https://example.com")

    async def test_unknown_tool_is_rejected(self):
        with self.assertRaises(ValueError):
            await execute_chat_tool("run_shell", {"command": "id"}, AsyncMock())


if __name__ == "__main__":
    unittest.main()
