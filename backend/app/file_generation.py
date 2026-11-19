import base64
import io
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from docx import Document
from openpyxl import Workbook


_ARABIC_FONT = "HamasaArabic"
_ARABIC_FONT_PATH = Path(__file__).with_name("fonts") / "Amiri-Regular.ttf.b64"


def _register_arabic_font():
    if _ARABIC_FONT in pdfmetrics.getRegisteredFontNames():
        return
    encoded = "".join(_ARABIC_FONT_PATH.read_text(encoding="ascii").split())
    font_bytes = base64.b64decode(encoded, validate=True)
    pdfmetrics.registerFont(TTFont(_ARABIC_FONT, io.BytesIO(font_bytes)))


def _pdf_rtl(text: str) -> str:
    # ReportLab does not perform Arabic shaping or bidirectional layout itself.
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(text))
    except ImportError as exc:
        raise RuntimeError("Arabic PDF support dependencies are missing.") from exc


def build_file(fmt: str, title: str, content: str, rows: list) -> bytes:
    if fmt == "docx":
        doc = Document()
        doc.add_heading(title, 0)
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("# "):
                doc.add_heading(line[2:], level=1)
            elif line.startswith("## "):
                doc.add_heading(line[3:], level=2)
            else:
                doc.add_paragraph(line)
        output = BytesIO()
        doc.save(output)
        return output.getvalue()

    if fmt == "pdf":
        _register_arabic_font()
        output = BytesIO()
        doc = SimpleDocTemplate(
            output, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm,
            topMargin=18*mm, bottomMargin=18*mm,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "HamasaArabicTitle", parent=styles["Title"],
            fontName=_ARABIC_FONT, alignment=TA_RIGHT,
            leading=24, fontSize=18, spaceAfter=8*mm,
        )
        body_style = ParagraphStyle(
            "HamasaArabicBody", parent=styles["BodyText"],
            fontName=_ARABIC_FONT, alignment=TA_RIGHT,
            leading=18, fontSize=11, wordWrap="RTL",
        )
        story = [Paragraph(escape(_pdf_rtl(title)), title_style), Spacer(1, 3*mm)]
        for line in content.splitlines():
            line = line.strip()
            if not line:
                story.append(Spacer(1, 3*mm))
                continue
            story.append(Paragraph(escape(_pdf_rtl(line)), body_style))
            story.append(Spacer(1, 2*mm))
        doc.build(story)
        return output.getvalue()

    if fmt == "xlsx":
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Hamasa"
        sheet.append([title])
        if content:
            sheet.append([content])
        for row in rows[:5000]:
            if isinstance(row, list):
                values = [
                    cell if isinstance(cell, (int, float, bool)) else str(cell)[:32000] if cell is not None else ""
                    for cell in row[:100]
                ]
                sheet.append(values)
                # Keep untrusted strings as text, never as executable spreadsheet formulas.
                for cell in sheet[sheet.max_row]:
                    if isinstance(cell.value, str):
                        cell.data_type = "s"
        for column in sheet.columns:
            letter = column[0].column_letter
            max_len = min(48, max((len(str(cell.value or "")) for cell in column), default=10))
            sheet.column_dimensions[letter].width = max(12, max_len + 2)
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()

    raise ValueError("Unsupported file format")
