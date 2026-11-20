import os
import base64
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from backend.app import main


class ImageGenerationTests(unittest.IsolatedAsyncioTestCase):
    async def test_image_generation_requires_explicit_image_model_configuration(self):
        body = main.ImageCreateRequest(prompt="A watercolor landscape")
        with patch.object(main, "API_KEY", "test-key"):
            with patch.dict(os.environ, {"AI_IMAGE_MODEL": ""}, clear=False):
                with self.assertRaises(HTTPException) as caught:
                    await main.generate_image(body)
        self.assertEqual(caught.exception.status_code, 503)

    async def test_generates_image_and_returns_data_url(self):
        image = base64.b64encode(b"fake-png").decode("ascii")
        captured = {}

        class FakeResponse:
            status_code = 200
            def json(self):
                return {"data": [{"b64_json": image, "revised_prompt": "A blue sea"}]}

        class FakeClient:
            def __init__(self, **kwargs):
                captured["options"] = kwargs
            async def __aenter__(self):
                return self
            async def __aexit__(self, exc_type, exc, tb):
                return False
            async def post(self, url, headers=None, json=None, data=None, files=None):
                captured.update({"url": url, "headers": headers, "json": json})
                return FakeResponse()

        body = main.ImageCreateRequest(prompt="A watercolor landscape")
        with patch.object(main, "API_KEY", "test-key"):
            with patch.object(main, "BASE_URL", "https://images.example/v1"):
                with patch.dict(os.environ, {"AI_IMAGE_MODEL": "image-test-model"}, clear=False):
                    with patch("backend.app.main.httpx.AsyncClient", FakeClient):
                        result = await main.generate_image(body)

        self.assertEqual(captured["url"], "https://images.example/v1/images/generations")
        self.assertEqual(captured["json"]["model"], "image-test-model")
        self.assertEqual(result["data_url"], "data:image/png;base64," + image)
        self.assertEqual(result["revised_prompt"], "A blue sea")

    async def test_image_edit_uses_multipart_and_rejects_invalid_base64(self):
        body = main.ImageCreateRequest(prompt="Remove the background", image_data="not-base64")
        with patch.object(main, "API_KEY", "test-key"):
            with patch.dict(os.environ, {"AI_IMAGE_MODEL": "image-test-model"}, clear=False):
                with self.assertRaises(HTTPException) as caught:
                    await main.generate_image(body)
        self.assertEqual(caught.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
