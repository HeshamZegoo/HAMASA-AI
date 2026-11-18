from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import mm
from docx import Document
from openpyxl import Workbook


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
        output = BytesIO()
        doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm,
                                topMargin=18*mm, bottomMargin=18*mm)
        styles = getSampleStyleSheet()
        story = [Paragraph(title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), styles["Title"]), Spacer(1, 8*mm)]
        for line in content.splitlines():
            line = line.strip()
            if not line:
                story.append(Spacer(1, 3*mm))
                continue
            safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(safe, styles["BodyText"]))
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
                sheet.append([str(cell)[:32000] if cell is not None else "" for cell in row[:100]])
        for column in sheet.columns:
            letter = column[0].column_letter
            max_len = min(48, max((len(str(cell.value or "")) for cell in column), default=10))
            sheet.column_dimensions[letter].width = max(12, max_len + 2)
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()

    raise ValueError("Unsupported file format")
