import re
from dataclasses import dataclass, replace

from app.pdf import PageText

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Chunk:
    page: int
    index: int  # running index within the document
    text: str
    section: str = ""  # e.g. "Kap. 6 Ledighetsförmåner, § 27 Semester"; empty when the text has no headings


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
    """Prefix every chunk with the document header and its section; searched and shown to the model, not to the user."""
    def head(c: Chunk) -> str:
        return " | ".join(part for part in (header, c.section) if part)

    return [replace(c, text=f"{head(c)}{HEADER_SEP}{c.text}") if head(c) else c for c in chunks]


def split_header(content: str) -> tuple[str, str]:
    """(document header, chunk text); the header is empty for chunks stored without one."""
    header, sep, body = content.partition(HEADER_SEP)
    return (header, body) if sep else ("", content)


def strip_header(content: str) -> str:
    """The chunk text as it appears on the page, without the document header."""
    return content.split(HEADER_SEP, 1)[1] if HEADER_SEP in content else content


# Heading styles. "agreement": "Kap. 6 Ledighetsförmåner" and "§ 27   Semester" (AB). "law": "2 kap. Arbetsmiljöns beskaffenhet"
# and "6 §   text" (SFS). Protocols also have "§ 317 Investeringar ...", but labelling them lowered retrieval (see eval/README.md).
# The title must start with a capital: "§ 28 mom. 9." at the start of a line is a reference, and table-of-contents lines
# have dot leaders.
_AGREEMENT_HEADING = re.compile(r"^(Kap\.\s*\d+|§\s*\d+)\s+[A-ZÅÄÖ].*$")
_LAW_CHAPTER = re.compile(r"^\d+\s?[a-z]?\s+kap\.\s+[A-ZÅÄÖ].*$")
_LAW_SECTION = re.compile(r"^(\d+\s?[a-z]?)\s§\s")


def heading_style(pages: list[PageText]) -> str | None:
    """"agreement" (three or more Kap. headings), "law" (ten or more "N §" paragraphs) or None. Labels only help these:
    on the six protocols they cost retrieval accuracy (MRR 0.977 -> 0.952 on dev, see eval/README.md)."""
    lines = [line.strip() for p in pages for line in p.text.splitlines()]
    if sum(1 for ln in lines if re.match(r"Kap\.\s*\d+\s+[A-ZÅÄÖ]", ln)) >= 3:
        return "agreement"
    if sum(1 for ln in lines if _LAW_SECTION.match(ln)) >= 10:
        return "law"
    return None


def _heading(line: str, style: str) -> tuple[str, str] | None:
    """("chapter" | "section", label) when the line starts a chapter or a section."""
    if style == "law":
        if _LAW_CHAPTER.match(line):
            return "chapter", line
        m = _LAW_SECTION.match(line)
        return ("section", f"{m.group(1)} §") if m else None
    if _AGREEMENT_HEADING.match(line) and "...." not in line and len(line) <= 120:
        return ("chapter" if line.startswith("Kap") else "section"), line
    return None


def _segments(text: str, chapter: str, para: str, style: str | None) -> list[tuple[str, str, str, str]]:
    """Split a page at its headings into (chapter, section, label, text); chapter and section carry over from earlier pages."""
    if not style:
        return [(chapter, para, "", text)]
    parts: list[tuple[str, str, str, str]] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            parts.append((chapter, para, ", ".join(x for x in (chapter, para) if x), "\n".join(buf)))
            buf.clear()

    for line in text.splitlines():
        found = _heading(" ".join(line.split()), style)
        if found:
            kind, label = found
            first = _heading(" ".join(buf[0].split()), style) if len(buf) == 1 else None
            lone_chapter = first is not None and first[0] == "chapter"
            if not lone_chapter:  # a chapter title alone is no chunk
                flush()
            if kind == "chapter":
                chapter, para = label, ""
            else:
                para = label
        buf.append(line)
    flush()
    return parts


def chunk_pages(pages: list[PageText], size: int = 900, overlap: int = 150, section_labels: bool | str | None = True) -> list[Chunk]:
    """Chunk page by page so every chunk keeps an exact page number for citations.

    With section_labels ("agreement", "law", or True for the first) a chunk never spans two headings and records the
    heading it sits under, also when that heading is on an earlier page."""
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")
    style = "agreement" if section_labels is True else (section_labels or None)

    chunks: list[Chunk] = []
    chapter = para = ""
    for page in pages:
        for chapter, para, label, text in _segments(page.text, chapter, para, style):
            current = ""
            for unit in _split_units(text, size):
                if current and len(current) + 1 + len(unit) > size:
                    chunks.append(Chunk(page.page, len(chunks), current, label))
                    tail = current[-overlap:] if overlap else ""
                    # Start the overlap at a word boundary.
                    current = tail.split(" ", 1)[1] if " " in tail else tail
                current = f"{current} {unit}".strip()
            if current:
                chunks.append(Chunk(page.page, len(chunks), current, label))
    return chunks
