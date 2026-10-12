from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MIN_CHARS_PER_DOCUMENT = 50


class PdfError(Exception):
    """The file could not be read as a PDF."""


class NoTextError(PdfError):
    """The PDF has no extractable text, e.g. a scanned document (OCR is not supported yet)."""


@dataclass(frozen=True)
class PageText:
    page: int  # 1-based
    text: str


def extract_pages(data: bytes) -> list[PageText]:
    try:
        reader = PdfReader(BytesIO(data))
        pages = [
            PageText(page=i, text=(p.extract_text() or "").strip())
            for i, p in enumerate(reader.pages, start=1)
        ]
    except (PdfReadError, ValueError, KeyError) as exc:
        raise PdfError(f"Kunde inte läsa PDF: {exc}") from exc

    if sum(len(p.text) for p in pages) < MIN_CHARS_PER_DOCUMENT:
        raise NoTextError("PDF:en innehåller ingen extraherbar text (troligen skannad).")
    return [p for p in pages if p.text]
