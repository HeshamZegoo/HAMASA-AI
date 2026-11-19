import base64
import io
import unittest
from unittest.mock import patch

from docx import Document
from openpyxl import load_workbook

from backend.app import main


class FakeGenerationResponse:
    status_code = 200
    def json(self):
        return {"choices": [{
            "message": {
                "content": '{"title":"Hamasa Report","message":"جهزت التقرير","content":"# Summary\\nUseful result","rows":[["Name","Count"],["Users",12]]}'
            }
        }]}


class FakeGenerationClient:
    payloads = []
    def __init__(self, **kwargs):
        pass
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        return False
    async def post(self, url, headers=None, json=None):
        self.payloads.append(json)
        return FakeGenerationResponse()


class FileGenerationEndpointTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        FakeGenerationClient.payloads = []

    async def test_docx_endpoint_returns_a_real_downloadable_document(self):
        body = main.FileCreateRequest(
            prompt="اعمل تقرير",
            format="docx",
            messages=[main.Message(role="user", content="اكتب تقريراً مختصراً")],
        )
        with patch.object(main, "API_KEY", "test-provider-key"):
            with patch("backend.app.main.httpx.AsyncClient", FakeGenerationClient):
                result = await main.generate_file(body)
        self.assertEqual(result["filename"], "Hamasa Report.docx")
        self.assertEqual(
            result["mime_type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        raw = base64.b64decode(result["data"])
        doc = Document(io.BytesIO(raw))
        text = "\n".join(p.text for p in doc.paragraphs)
        self.assertIn("Summary", text)
        self.assertIn("Useful result", text)
        self.assertEqual(FakeGenerationClient.payloads[0]["response_format"]["type"], "json_object")

    async def test_xlsx_endpoint_preserves_numeric_values(self):
        body = main.FileCreateRequest(prompt="اعمل جدول", format="xlsx")
        with patch.object(main, "API_KEY", "test-provider-key"):
            with patch("backend.app.main.httpx.AsyncClient", FakeGenerationClient):
                result = await main.generate_file(body)
        workbook = load_workbook(io.BytesIO(base64.b64decode(result["data"]), validate=False), data_only=True)
        sheet = workbook.active
        self.assertEqual(sheet["B3"].value, 12)
        self.assertEqual(sheet["B3"].data_type, "n")
        workbook.close()


if __name__ == "__main__":
    unittest.main()
