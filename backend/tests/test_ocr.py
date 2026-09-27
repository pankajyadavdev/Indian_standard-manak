import io

import pytest
from reportlab.pdfgen import canvas

from app.services.document_processor import DocumentValidationError, extract_text_from_pdf


def _sparse_pdf():
    output = io.BytesIO()
    page = canvas.Canvas(output)
    page.drawString(50, 800, "A")
    page.save()
    return output.getvalue()


def test_scanned_pdf_uses_real_pdf_render_and_ocr(monkeypatch):
    from app.services import document_processor

    monkeypatch.setattr(document_processor.pytesseract, "image_to_string", lambda image, **kwargs: "Recognized tender text: IS 456")
    text, pages, ocr_applied = extract_text_from_pdf(_sparse_pdf())

    assert pages == 1
    assert ocr_applied is True
    assert "Recognized tender text: IS 456" in text
    assert "[OCR Extracted Content for Scanned Page" not in text


def test_scanned_pdf_fails_clearly_when_ocr_returns_no_text(monkeypatch):
    from app.services import document_processor

    monkeypatch.setattr(document_processor.pytesseract, "image_to_string", lambda image, **kwargs: " ")
    with pytest.raises(DocumentValidationError, match="could not be read by OCR"):
        extract_text_from_pdf(_sparse_pdf())
