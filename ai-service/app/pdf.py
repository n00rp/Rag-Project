from dataclasses import dataclass
from io import BytesIO

import pdfplumber
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.columns import column_text
from app.text import normalize_text

MIN_CHARS_PER_DOCUMENT = 50


class PdfError(Exception):
    """The file could not be read as a PDF."""


class NoTextError(PdfError):
    """The PDF has no extractable text, e.g. a scanned document (OCR is not supported yet)."""


@dataclass(frozen=True)
class PageText:
    page: int  # 1-based
    text: str


def _column_pages(data: bytes) -> dict[int, str]:
    """Text of the pages that have a two-column block, read column by column (see app/columns.py).
    Best effort: any failure leaves the pypdf text in place."""
    try:
        with pdfplumber.open(BytesIO(data)) as pdf:
            found = {}
            for i, page in enumerate(pdf.pages, start=1):
                text = column_text(page.extract_words(), page.width)
                if text:
                    found[i] = text
            return found
    except Exception:  # noqa: BLE001 - pdfplumber/pdfminer raise many types on odd files
        return {}


def extract_pages(data: bytes) -> list[PageText]:
    try:
        reader = PdfReader(BytesIO(data))
        columns = _column_pages(data)
        pages = [
            PageText(page=i, text=normalize_text(columns.get(i) or p.extract_text() or "").strip())
            for i, p in enumerate(reader.pages, start=1)
        ]
    except (PdfReadError, ValueError, KeyError) as exc:
        raise PdfError(f"Kunde inte läsa PDF: {exc}") from exc

    if sum(len(p.text) for p in pages) < MIN_CHARS_PER_DOCUMENT:
        raise NoTextError("PDF:en innehåller ingen extraherbar text (troligen skannad).")
    return [p for p in pages if p.text]
