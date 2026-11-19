import base64
import io
import unittest
from unittest.mock import patch

from docx import Document
from openpyxl import load_workbook
from pypdf import PdfReader

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


class FakeVisionThenGenerationClient:
    payloads = []
    calls = 0
    def __init__(self, **kwargs):
        pass
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        return False
    async def post(self, url, headers=None, json=None):
        self.payloads.append(json)
        self.calls += 1
        if self.calls == 1:
            class VisionResponse:
                status_code = 200
                def json(self):
                    return {"choices": [{"message": {"content": "الصورة تعرض فاتورة بإجمالي 1250 جنيه."}}]}
            return VisionResponse()
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

    async def test_pdf_endpoint_returns_a_real_readable_pdf(self):
        body = main.FileCreateRequest(
            prompt="اعمل تقرير PDF",
            format="pdf",
            messages=[main.Message(role="user", content="اكتب تقريراً عن النتائج")],
        )
        with patch.object(main, "API_KEY", "test-provider-key"):
            with patch("backend.app.main.httpx.AsyncClient", FakeGenerationClient):
                result = await main.generate_file(body)
        raw = base64.b64decode(result["data"])
        self.assertTrue(raw.startswith(b"%PDF-"))
        reader = PdfReader(io.BytesIO(raw))
        self.assertGreaterEqual(len(reader.pages), 1)
        extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertIn("Useful result", extracted)
        self.assertEqual(result["mime_type"], "application/pdf")

    async def test_image_attachment_is_analyzed_then_used_to_create_pdf(self):
        FakeVisionThenGenerationClient.payloads = []
        FakeVisionThenGenerationClient.calls = 0
        body = main.FileCreateRequest(
            prompt="اعمل PDF يلخص الصورة",
            format="pdf",
            messages=[main.Message(role="user", content="لخص الصورة في تقرير")],
            attachments=[main.AttachmentInput(
                name="invoice.png", mime_type="image/png",
                data=base64.b64encode(b"\x89PNG\r\n\x1a\nimage-bytes").decode("ascii")
            )],
        )
        with patch.object(main, "API_KEY", "test-provider-key"):
            with patch.object(main, "BASE_URL", "https://integrate.api.nvidia.com/v1"):
                with patch.object(main, "MODEL", "meta/llama-3.3-70b-instruct"):
                    with patch("backend.app.main.httpx.AsyncClient", FakeVisionThenGenerationClient):
                        result = await main.generate_file(body)
        self.assertEqual(len(FakeVisionThenGenerationClient.payloads), 2)
        vision_payload, generation_payload = FakeVisionThenGenerationClient.payloads
        self.assertEqual(vision_payload["model"], "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning")
        self.assertNotIn("response_format", vision_payload)
        self.assertIn("data:image/png;base64,", str(vision_payload))
        self.assertEqual(generation_payload["model"], "meta/llama-3.3-70b-instruct")
        self.assertEqual(generation_payload["response_format"]["type"], "json_object")
        self.assertTrue(any(
            "الصورة تعرض فاتورة" in str(message.get("content"))
            for message in generation_payload["messages"]
        ))
        self.assertTrue(base64.b64decode(result["data"]).startswith(b"%PDF-"))

    async def test_xlsx_endpoint_preserves_numeric_values(self):
        body = main.FileCreateRequest(prompt="اعمل جدول", format="xlsx")
        with patch.object(main, "API_KEY", "test-provider-key"):
            with patch("backend.app.main.httpx.AsyncClient", FakeGenerationClient):
                result = await main.generate_file(body)
        workbook = load_workbook(io.BytesIO(base64.b64decode(result["data"])), data_only=True)
        sheet = workbook.active
        self.assertEqual(sheet["B4"].value, 12)
        self.assertEqual(sheet["B4"].data_type, "n")
        workbook.close()


if __name__ == "__main__":
    unittest.main()
