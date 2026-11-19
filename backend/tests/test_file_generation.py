import io
import unittest

from docx import Document
from openpyxl import load_workbook
from pypdf import PdfReader
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

from backend.app.file_generation import build_file


class FileGenerationTests(unittest.TestCase):
    def test_docx_contains_title_headings_and_body(self):
        raw = build_file("docx", "HAMASA Report", "# Summary\nImportant result", [])
        document = Document(io.BytesIO(raw))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        self.assertIn("HAMASA Report", text)
        self.assertIn("Summary", text)
        self.assertIn("Important result", text)

    def test_arabic_docx_paragraphs_use_right_to_left_direction(self):
        raw = build_file("docx", "تقرير حماصة", "ملخص\nالنتيجة المهمة", [])
        document = Document(io.BytesIO(raw))
        arabic_paragraph = document.paragraphs[1]
        self.assertEqual(arabic_paragraph.alignment, WD_ALIGN_PARAGRAPH.RIGHT)
        self.assertIsNotNone(arabic_paragraph._p.pPr.find(qn("w:bidi")))
        self.assertIsNotNone(arabic_paragraph.runs[0]._element.rPr.find(qn("w:rtl")))

    def test_pdf_is_valid_and_contains_document_text(self):
        raw = build_file("pdf", "HAMASA Report", "Summary\nImportant result", [])
        reader = PdfReader(io.BytesIO(raw))
        self.assertGreaterEqual(len(reader.pages), 1)
        extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertIn("HAMASA Report", extracted)
        self.assertIn("Important result", extracted)

    def test_arabic_pdf_generates_valid_pages_with_embedded_font(self):
        raw = build_file("pdf", "تقرير حماصة", "ملخص بالعربية\nالنتيجة النهائية", [])
        reader = PdfReader(io.BytesIO(raw))
        self.assertGreaterEqual(len(reader.pages), 1)
        resources = reader.pages[0]["/Resources"]
        self.assertIn("/Font", resources)

    def test_xlsx_contains_title_description_and_rows(self):
        raw = build_file("xlsx", "Sales", "Monthly totals", [["Month", "Total"], ["January", 10], ["Formula", "=1+1"]],)
        workbook = load_workbook(io.BytesIO(raw), data_only=True)
        sheet = workbook.active
        self.assertEqual(sheet["A1"].value, "Sales")
        self.assertEqual(sheet["A2"].value, "Monthly totals")
        self.assertEqual(sheet["A3"].value, "Month")
        self.assertEqual(sheet["B4"].value, 10)
        self.assertEqual(sheet["B4"].data_type, "n")
        self.assertEqual(sheet["A5"].value, "Formula")
        self.assertEqual(sheet["B5"].value, "=1+1")
        self.assertEqual(sheet["B5"].data_type, "s")
        workbook.close()

    def test_pdf_renders_markdown_table_and_explicit_three_pages(self):
        content = (
            "# الصفحة الأولى\nمقدمة عن الذكاء الاصطناعي\n"
            "| Domain | Use |\n|---|---|\n| Health | Image review |\n"
            "[[PAGE_BREAK]]\n"
            "# الصفحة الثانية\nتطبيقات عملية\nفقرة توضيحية\n"
            "[[PAGE_BREAK]]\n"
            "# الصفحة الثالثة\nالتحديات والخلاصة\nنهاية التقرير"
        )
        raw = build_file("pdf", "تقرير الذكاء الاصطناعي", content, [], page_count=3)
        reader = PdfReader(io.BytesIO(raw))
        self.assertEqual(len(reader.pages), 3)
        extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertIn("Health", extracted)
        self.assertIn("Health", extracted)

    def test_pdf_rejects_wrong_explicit_page_count(self):
        with self.assertRaisesRegex(ValueError, "عدد صفحات PDF غير مطابق"):
            build_file("pdf", "تقرير", "صفحة واحدة فقط", [], page_count=3)

    def test_arabic_xlsx_uses_right_to_left_sheet_view(self):
        raw = build_file("xlsx", "تقرير", "إجمالي المبيعات", [["المنتج", "الكمية"]],)
        workbook = load_workbook(io.BytesIO(raw), data_only=True)
        self.assertTrue(workbook.active.sheet_view.rightToLeft)
        workbook.close()

    def test_docx_renders_markdown_table_as_real_table(self):
        raw = build_file("docx", "Report", "# Summary\n| Name | Score |\n|---|---|\n| Ada | 99 |", [])
        document = Document(io.BytesIO(raw))
        self.assertEqual(len(document.tables), 1)
        self.assertEqual(document.tables[0].cell(1, 0).text, "Ada")

    def test_pptx_creates_slides_from_markdown_headings(self):
        from pptx import Presentation
        raw = build_file("pptx", "Deck", "# Intro\nWelcome\n# Results\nDone", [])
        deck = Presentation(io.BytesIO(raw))
        self.assertEqual(len(deck.slides), 2)
        self.assertIn("Intro", deck.slides[0].shapes[0].text)
        self.assertIn("Results", deck.slides[1].shapes[0].text)
        raw_crlf = build_file("pptx", "Deck", "# One\\r\\nLine one\\r\\n# Two\\r\\nLine two", [])
        self.assertEqual(len(Presentation(io.BytesIO(raw_crlf)).slides), 2)

    def test_csv_json_markdown_and_html_outputs(self):
        import json
        csv_raw = build_file("csv", "Data", "", [["Name", "Value"], ["A", 2]])
        self.assertTrue(csv_raw.startswith(b"\\xef\\xbb\\xbf"))
        self.assertIn("Name,Value", csv_raw.decode("utf-8-sig"))
        json_raw = build_file("json", "تقرير", "محتوى", [["أ", 1]])
        self.assertEqual(json.loads(json_raw)["title"], "تقرير")
        md_raw = build_file("md", "Guide", "## Intro", [])
        self.assertIn("# Guide", md_raw.decode("utf-8"))
        html_raw = build_file("html", "<script>", "<b>hello</b>", [])
        self.assertIn("&lt;script&gt;", html_raw.decode("utf-8"))
        self.assertNotIn("<script>", html_raw.decode("utf-8"))

    def test_unsupported_format_is_rejected(self):
        with self.assertRaises(ValueError):
            build_file("exe", "Title", "Body", [])


if __name__ == "__main__":
    unittest.main()
