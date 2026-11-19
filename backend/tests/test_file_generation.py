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

    def test_arabic_xlsx_uses_right_to_left_sheet_view(self):
        raw = build_file("xlsx", "تقرير", "إجمالي المبيعات", [["المنتج", "الكمية"]],)
        workbook = load_workbook(io.BytesIO(raw), data_only=True)
        self.assertTrue(workbook.active.sheet_view.rightToLeft)
        workbook.close()

    def test_unsupported_format_is_rejected(self):
        with self.assertRaises(ValueError):
            build_file("csv", "Title", "Body", [])


if __name__ == "__main__":
    unittest.main()
