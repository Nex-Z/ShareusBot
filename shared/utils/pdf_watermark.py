from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas


def _build_watermark_page(width: float, height: float, text: str) -> BytesIO:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    c.saveState()
    c.setFillColor(Color(0.45, 0.45, 0.45, alpha=0.14))
    c.setFont("Helvetica", 24)
    c.translate(width / 2, height / 2)
    c.rotate(35)
    c.drawCentredString(0, 0, text)
    c.restoreState()
    c.save()
    buf.seek(0)
    return buf


def apply_pdf_watermark(input_path: Path, output_path: Path, watermark_text: str) -> Path:
    reader = PdfReader(str(input_path))
    writer = PdfWriter()

    text = (watermark_text or "").strip()
    if not text:
        text = "shareus.top"

    for page in reader.pages:
        box = page.mediabox
        width = float(box.width)
        height = float(box.height)
        wm_buf = _build_watermark_page(width, height, text)
        wm_page = PdfReader(wm_buf).pages[0]
        page.merge_page(wm_page)
        writer.add_page(page)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as f:
        writer.write(f)

    return output_path

