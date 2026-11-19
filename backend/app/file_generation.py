import base64
import io
import re
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from openpyxl import Workbook
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor as PptRGBColor

_ARABIC_FONT = "HamasaArabic"
_ARABIC_FONT_PATH = Path(__file__).with_name("fonts") / "Amiri-Regular.ttf.b64"
_PAGE_BREAK = re.compile(r"^\s*(?:\[\[PAGE_BREAK\]\]|<!--\s*pagebreak\s*-->|---PAGE BREAK---)\s*$", re.I)
_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F]")

def _register_arabic_font():
    if _ARABIC_FONT in pdfmetrics.getRegisteredFontNames():
        return
    encoded = "".join(_ARABIC_FONT_PATH.read_text(encoding="ascii").split())
    font_bytes = base64.b64decode(encoded, validate=True)
    pdfmetrics.registerFont(TTFont(_ARABIC_FONT, io.BytesIO(font_bytes)))

def _apply_docx_direction(paragraph, text: str) -> None:
    if not _ARABIC_RE.search(text):
        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        return
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    paragraph_properties = paragraph._p.get_or_add_pPr()
    if paragraph_properties.find(qn("w:bidi")) is None:
        paragraph_properties.append(OxmlElement("w:bidi"))
    for run in paragraph.runs:
        run_properties = run._element.get_or_add_rPr()
        if run_properties.find(qn("w:rtl")) is None:
            run_properties.append(OxmlElement("w:rtl"))
        run.font.name = "Arial"
        run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "Arial")

def _pdf_rtl(text: str) -> str:
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(text))
    except ImportError as exc:
        raise RuntimeError("Arabic PDF support dependencies are missing.") from exc

def _table_cells(line: str) -> list[str]:
    value = line.strip().strip("|")
    return [part.strip() for part in value.split("|")]

def _build_pdf(title: str, content: str, page_count: int = 0) -> bytes:
    _register_arabic_font()
    output = BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=A4, rightMargin=17*mm, leftMargin=17*mm,
        topMargin=17*mm, bottomMargin=20*mm, title=title,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "HamasaArabicTitle", parent=styles["Title"], fontName=_ARABIC_FONT,
        alignment=TA_RIGHT, leading=27, fontSize=20, textColor=colors.HexColor("#17324D"),
        spaceAfter=7*mm,
    )
    h1 = ParagraphStyle(
        "HamasaArabicH1", parent=styles["Heading1"], fontName=_ARABIC_FONT,
        alignment=TA_RIGHT, leading=23, fontSize=15, textColor=colors.HexColor("#176B87"),
        spaceBefore=4*mm, spaceAfter=2*mm,
    )
    h2 = ParagraphStyle(
        "HamasaArabicH2", parent=styles["Heading2"], fontName=_ARABIC_FONT,
        alignment=TA_RIGHT, leading=20, fontSize=12.5, textColor=colors.HexColor("#176B87"),
        spaceBefore=3*mm, spaceAfter=1.5*mm,
    )
    body = ParagraphStyle(
        "HamasaArabicBody", parent=styles["BodyText"], fontName=_ARABIC_FONT,
        alignment=TA_RIGHT, leading=17, fontSize=10.5, wordWrap="RTL",
        spaceAfter=2.5*mm,
    )
    cell_style = ParagraphStyle(
        "HamasaArabicCell", parent=body, fontSize=8.5, leading=12,
        spaceAfter=0, alignment=TA_RIGHT,
    )
    header_style = ParagraphStyle(
        "HamasaArabicHeader", parent=cell_style, textColor=colors.white,
        alignment=TA_CENTER,
    )
    story = [Paragraph(escape(_pdf_rtl(title)), title_style)]
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            story.append(Spacer(1, 1.5*mm)); i += 1; continue
        if _PAGE_BREAK.match(line):
            story.append(PageBreak()); i += 1; continue
        # Markdown pipe tables: header, separator, then one or more data rows.
        if "|" in line and i + 1 < len(lines) and _TABLE_RULE.match(lines[i + 1]):
            raw_rows = [_table_cells(line)]
            i += 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                raw_rows.append(_table_cells(lines[i]))
                i += 1
            width = max(len(row) for row in raw_rows)
            table_data = []
            for row_index, row in enumerate(raw_rows):
                row = row + [""] * (width - len(row))
                style = header_style if row_index == 0 else cell_style
                table_data.append([Paragraph(escape(_pdf_rtl(value)), style) for value in row])
            available = A4[0] - 34*mm
            table = Table(table_data, colWidths=[available/width]*width, repeatRows=1, hAlign="RIGHT")
            table.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#176B87")),
                ("GRID", (0,0), (-1,-1), 0.45, colors.HexColor("#C8D6DF")),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F2F7FA")]),
                ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                ("LEFTPADDING", (0,0), (-1,-1), 6), ("RIGHTPADDING", (0,0), (-1,-1), 6),
                ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ]))
            story.extend([Spacer(1, 2*mm), table, Spacer(1, 3*mm)])
            continue
        if line.startswith("# "):
            story.append(Paragraph(escape(_pdf_rtl(line[2:].strip())), h1))
        elif line.startswith("## ") or line.startswith("### "):
            story.append(Paragraph(escape(_pdf_rtl(line.lstrip("#").strip())), h2))
        elif line.startswith(("- ", "* ", "• ")):
            story.append(Paragraph(escape(_pdf_rtl("• " + line[2:].strip())), body))
        else:
            story.append(Paragraph(escape(_pdf_rtl(line)), body))
        i += 1

    def footer(canvas, page_doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D7E2E8"))
        canvas.line(17*mm, 14*mm, A4[0]-17*mm, 14*mm)
        canvas.setFont(_ARABIC_FONT, 8)
        canvas.setFillColor(colors.HexColor("#6B7C88"))
        canvas.drawCentredString(A4[0]/2, 8*mm, _pdf_rtl(f"حماصة • صفحة {page_doc.page}"))
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    raw = output.getvalue()
    if page_count:
        from pypdf import PdfReader
        actual_pages = len(PdfReader(BytesIO(raw)).pages)
        if actual_pages != page_count:
            raise ValueError(
                f"عدد صفحات PDF غير مطابق: المطلوب {page_count} صفحة، الناتج {actual_pages}. "
                "أعد إنشاء المحتوى مع فواصل [[PAGE_BREAK]] واضحة بين الصفحات."
            )
    return raw

def build_file(fmt: str, title: str, content: str, rows: list, page_count: int = 0) -> bytes:
    if fmt == "docx":
        doc = Document()
        title_paragraph = doc.add_heading(title, 0)
        _apply_docx_direction(title_paragraph, title)
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("# "):
                heading = doc.add_heading(line[2:], level=1)
                _apply_docx_direction(heading, line[2:])
            elif line.startswith("## "):
                heading = doc.add_heading(line[3:], level=2)
                _apply_docx_direction(heading, line[3:])
            else:
                paragraph = doc.add_paragraph(line)
                _apply_docx_direction(paragraph, line)
        output = BytesIO()
        doc.save(output)
        return output.getvalue()
    if fmt == "pdf":
        return _build_pdf(title, content, page_count)
    if fmt == "xlsx":
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Hamasa"
        spreadsheet_text = " ".join([title, content] + [
            str(value) for row in rows[:5000] if isinstance(row, list)
            for value in row[:100] if value is not None
        ])
        sheet.sheet_view.rightToLeft = bool(_ARABIC_RE.search(spreadsheet_text))
        sheet.append([title])
        if content:
            sheet.append([content])
        for row in rows[:5000]:
            if isinstance(row, list):
                values = [cell if isinstance(cell, (int, float, bool)) else str(cell)[:32000] if cell is not None else "" for cell in row[:100]]
                sheet.append(values)
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

    if fmt == "pptx":
        presentation = Presentation()
        presentation.slide_width = Inches(13.333)
        presentation.slide_height = Inches(7.5)
        sections = []
        current = {"title": title, "body": []}
        for line in content.replace("\\r", "").splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("# "):
                if current["body"] or current["title"] != title:
                    sections.append(current)
                current = {"title": line[2:].strip(), "body": []}
            else:
                current["body"].append(line)
        if current["body"] or not sections:
            sections.append(current)
        for section in sections:
            slide = presentation.slides.add_slide(presentation.slide_layouts[6])
            slide.background.fill.solid()
            slide.background.fill.fore_color.rgb = PptRGBColor(247, 249, 251)
            title_box = slide.shapes.add_textbox(Inches(.65), Inches(.45), Inches(12), Inches(.8))
            paragraph = title_box.text_frame.paragraphs[0]
            paragraph.text = section["title"]
            paragraph.font.size = Pt(28)
            paragraph.font.bold = True
            paragraph.font.color.rgb = PptRGBColor(23, 50, 77)
            paragraph.alignment = 2 if _ARABIC_RE.search(section["title"]) else 0
            body_box = slide.shapes.add_textbox(Inches(.8), Inches(1.55), Inches(11.7), Inches(5.3))
            frame = body_box.text_frame
            frame.word_wrap = True
            for index, text in enumerate(section["body"][:18]):
                paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
                paragraph.text = text[2:] if text.startswith(("- ", "* ", "• ")) else text
                paragraph.font.size = Pt(17)
                paragraph.space_after = Pt(12)
                paragraph.alignment = 2 if _ARABIC_RE.search(text) else 0
        output = BytesIO()
        presentation.save(output)
        return output.getvalue()
    if fmt in ("txt", "md"):
        prefix = "# " if fmt == "md" else ""
        return (prefix + title + "\\n\\n" + content).encode("utf-8")
    if fmt == "csv":
        import csv
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        for row in rows:
            if isinstance(row, list):
                writer.writerow(row[:100])
        return ("\\ufeff" + output.getvalue()).encode("utf-8")
    if fmt == "json":
        import json
        return json.dumps({"title": title, "content": content, "rows": rows}, ensure_ascii=False, indent=2).encode("utf-8")
    if fmt == "html":
        from html import escape as html_escape
        return ("<!doctype html><html lang='ar'><meta charset='utf-8'><title>" + html_escape(title) + "</title><main dir='auto'><h1>" + html_escape(title) + "</h1><pre>" + html_escape(content) + "</pre></main></html>").encode("utf-8")
    raise ValueError("Unsupported file format")
