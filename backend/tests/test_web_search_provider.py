import os
import unittest
from unittest.mock import patch

from backend.app import main


class FakeResponse:
    status_code = 200

    def json(self):
        return {
            "results": [
                {
                    "title": "Official result",
                    "url": "https://example.com/docs",
                    "content": "Relevant documentation",
                    "published_date": "2026-11-19",
                }
            ]
        }


class FakeClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.request_url = None
        self.request_body = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json):
        self.request_url = url
        self.request_body = json
        return FakeResponse()


class LiveWebSearchTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_uses_server_key_and_cost_efficient_defaults(self):
        fake_client = FakeClient()
        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-secret"}):
            with patch("backend.app.main.httpx.AsyncClient", return_value=fake_client):
                results = await main._live_web_search("latest FastAPI version")

        self.assertEqual(len(results), 1)
        self.assertEqual(fake_client.request_url, "https://api.tavily.com/search")
        self.assertEqual(fake_client.request_body["api_key"], "test-secret")
        self.assertEqual(fake_client.request_body["search_depth"], "advanced")
        self.assertEqual(fake_client.request_body["max_results"], 8)
        self.assertFalse(fake_client.request_body["include_answer"])
        self.assertEqual(fake_client.request_body["include_raw_content"], "markdown")
        self.assertEqual(fake_client.request_body["chunks_per_source"], 3)

    async def test_search_is_disabled_without_server_key(self):
        with patch.dict(os.environ, {"TAVILY_API_KEY": ""}):
            with patch("backend.app.main.httpx.AsyncClient") as client:
                results = await main._live_web_search("latest FastAPI version")
        self.assertEqual(results, [])
        client.assert_not_called()

    async def test_query_is_bounded_before_sending(self):
        fake_client = FakeClient()
        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-secret"}):
            with patch("backend.app.main.httpx.AsyncClient", return_value=fake_client):
                await main._live_web_search("x" * 900)
        self.assertEqual(len(fake_client.request_body["query"]), 400)


    async def test_news_search_is_fresh_and_filters_social_results(self):
        class NewsResponse:
            status_code = 200
            def json(self):
                return {"results": [
                    {"title": "Social post", "url": "https://www.facebook.com/groups/1/posts/2", "content": "not an article"},
                    {"title": "AI report", "url": "https://www.reuters.com/technology/ai/", "content": "AI industry news"},
                ]}
        class NewsClient(FakeClient):
            async def post(self, url, json):
                self.request_url = url
                self.request_body = json
                return NewsResponse()
        fake_client = NewsClient()
        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-secret"}):
            with patch("backend.app.main.httpx.AsyncClient", return_value=fake_client):
                results = await main._live_web_search("أحدث أخبار الذكاء الاصطناعي اليوم")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "AI report")
        self.assertEqual(fake_client.request_body["topic"], "news")
        self.assertEqual(fake_client.request_body["days"], 1)
        self.assertGreaterEqual(fake_client.request_body["max_results"], 5)
        self.assertEqual(fake_client.request_body["query"], "أحدث أخبار الذكاء الاصطناعي اليوم")
        self.assertIn("facebook.com", fake_client.request_body["exclude_domains"])


if __name__ == "__main__":
    unittest.main()
