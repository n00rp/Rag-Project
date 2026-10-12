import re
from dataclasses import dataclass

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
