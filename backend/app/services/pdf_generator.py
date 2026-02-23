"""
Generate PDF from plain text. Used when user edits resume content.
"""
from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from backend.app.core.logging_config import get_logger

logger = get_logger("services.pdf_generator")


def text_to_pdf_bytes(text: str, title: str = "Resume") -> bytes:
    """
    Generate a PDF from plain text. Preserves line breaks.
    Returns PDF file content as bytes.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = inch
    x, y = margin, height - margin
    line_height = 14
    c.setFont("Helvetica", 14)
    c.drawString(x, y, title[:80])
    y -= line_height * 1.5
    c.setFont("Helvetica", 10)
    body = (text or "").strip()
    if body:
        for line in body.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            if y < margin + line_height:
                c.showPage()
                c.setFont("Helvetica", 10)
                y = height - margin
            c.drawString(x, y, (line[:120] + "..") if len(line) > 120 else line)
            y -= line_height
    else:
        c.drawString(x, y, "(No content)")
    c.save()
    return buffer.getvalue()
