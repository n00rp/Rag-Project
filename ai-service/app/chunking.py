import re
from dataclasses import dataclass, replace

from app.pdf import PageText

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Chunk:
    page: int
    index: int  # running index within the document
    text: str


def _split_units(text: str, size: int) -> list[str]:
    """Split into paragraphs, then sentences, then hard-wrap anything still too long."""
    units: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = " ".join(para.split())
        if not para:
            continue
        if len(para) <= size:
            units.append(para)
            continue
        for sent in _SENTENCE_END.split(para):
            while len(sent) > size:
                cut = sent.rfind(" ", 0, size)
                cut = cut if cut > 0 else size  # no space at all: hard cut
                units.append(sent[:cut].strip())
                sent = sent[cut:].strip()
            if sent:
                units.append(sent)
    return units


def document_header(pages: list[PageText], max_lines: int = 3, max_chars: int = 200) -> str:
    """Document context taken from the first page, e.g. 'Protokoll nr 8 Sammanträdesdatum: 2025-04-09 Kommunstyrelsen'.

    Repeated page headers are stripped before chunking, but the date and body they name are exactly what
    questions refer to ("sammanträdet 2025-04-09"), so every chunk starts with this line again (see eval/README.md).
    """
    lines = [ln.strip() for ln in pages[0].text.splitlines() if ln.strip()] if pages else []
    return " ".join(lines[:max_lines])[:max_chars]


# Chunk text never contains a line break (units are joined with spaces), so one separates the header.
HEADER_SEP = "\n"


def add_header(chunks: list[Chunk], header: str) -> list[Chunk]:
    """Prefix every chunk with the document header; it is searched and shown to the model, not to the user."""
    if not header:
        return chunks
    return [replace(c, text=f"{header}{HEADER_SEP}{c.text}") for c in chunks]


def strip_header(content: str) -> str:
    """The chunk text as it appears on the page, without the document header."""
    return content.split(HEADER_SEP, 1)[1] if HEADER_SEP in content else content


def chunk_pages(pages: list[PageText], size: int = 900, overlap: int = 150) -> list[Chunk]:
    """Chunk page by page so every chunk keeps an exact page number for citations."""
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")

    chunks: list[Chunk] = []
    for page in pages:
        current = ""
        for unit in _split_units(page.text, size):
            if current and len(current) + 1 + len(unit) > size:
                chunks.append(Chunk(page.page, len(chunks), current))
                tail = current[-overlap:] if overlap else ""
                # Start the overlap at a word boundary.
                current = tail.split(" ", 1)[1] if " " in tail else tail
            current = f"{current} {unit}".strip()
        if current:
            chunks.append(Chunk(page.page, len(chunks), current))
    return chunks
