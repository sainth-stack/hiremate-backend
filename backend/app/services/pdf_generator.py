"""
Generate PDF from plain text. Used when user edits resume content.
"""
from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from backend.app.core.config import PDF_DEFAULT_TITLE, PDF_FONT_SIZE_BODY, PDF_FONT_SIZE_TITLE, PDF_LINE_HEIGHT, PDF_MAX_LINE_CHARS
from backend.app.core.logging_config import get_logger

logger = get_logger("services.pdf_generator")


def text_to_pdf_bytes(text: str, title: str | None = None) -> bytes:
    """
    Generate a PDF from plain text. Preserves line breaks.
    Returns PDF file content as bytes.
    """
    title_val = title or PDF_DEFAULT_TITLE
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = inch
    x, y = margin, height - margin
    c.setFont("Helvetica", PDF_FONT_SIZE_TITLE)
    c.drawString(x, y, title_val[:80])
    y -= PDF_LINE_HEIGHT * 1.5
    c.setFont("Helvetica", PDF_FONT_SIZE_BODY)
    body = (text or "").strip()
    if body:
        for line in body.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            if y < margin + PDF_LINE_HEIGHT:
                c.showPage()
                c.setFont("Helvetica", PDF_FONT_SIZE_BODY)
                y = height - margin
            c.drawString(x, y, (line[:PDF_MAX_LINE_CHARS] + "..") if len(line) > PDF_MAX_LINE_CHARS else line)
            y -= PDF_LINE_HEIGHT
    else:
        c.drawString(x, y, "(No content)")
    c.save()
    return buffer.getvalue()
