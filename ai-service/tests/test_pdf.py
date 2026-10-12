import pytest

from app.pdf import NoTextError, PdfError, extract_pages
from tests.conftest import make_pdf


def test_extracts_text_per_page_with_swedish_characters():
    data = make_pdf(
        ["Kommunstyrelsen beslutade om skolskjuts för åk 1-6 i området.", "Budgeten för kultur ökar på nästa år."]
    )
    pages = extract_pages(data)
    assert [p.page for p in pages] == [1, 2]
    assert "skolskjuts" in pages[0].text
    assert "åk" in pages[0].text


def test_garbage_is_a_pdf_error():
    with pytest.raises(PdfError):
        extract_pages(b"not a pdf")


def test_pdf_without_text_is_rejected():
    with pytest.raises(NoTextError):
        extract_pages(make_pdf([""]))
