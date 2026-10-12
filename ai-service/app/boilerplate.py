import math
import re
from collections import Counter

from app.pdf import PageText

# Documents shorter than this don't have enough pages to tell a header from real content.
MIN_PAGES = 4
# Running headers/footers sit at the very top/bottom of a page. Looking only there keeps templated
# body lines from being mistaken for boilerplate.
HEAD_LINES = 6
TAIL_LINES = 3


def _line_keys(line: str, page: int) -> set[str]:
    """Keys a line can match on: its whitespace-normalized text, and the same text with the page's own number masked.

    "Göteborgs Stad protokoll 3 (56)" on page 3 and "... protokoll 17 (56)" on page 17 share the masked key,
    while every other number must match exactly. Masking *all* digits would also make real content such as
    "§ 289 Ärendenummer SLK-2025-00035" look like a repeating header, and those are the lines people search for.
    The exact key is kept as well so a constant like "Protokoll nr 3" still matches on page 3 itself, and a variant
    masking only the first occurrence handles the last page, where "protokoll 56 (56)" must match "protokoll 3 (56)".
    """
    text = " ".join(line.split())
    number = rf"(?<!\d){page}(?!\d)"
    return {text, re.sub(number, "#P#", text, count=1), re.sub(number, "#P#", text)}


def _edge_indexes(lines: list[str]) -> set[int]:
    """Indexes of the first HEAD_LINES and last TAIL_LINES non-blank lines (PDFs interleave blank lines)."""
    filled = [i for i, ln in enumerate(lines) if ln.strip()]
    return set(filled[:HEAD_LINES]) | set(filled[-TAIL_LINES:])


def strip_repeated_lines(pages: list[PageText], threshold: float = 0.5) -> list[PageText]:
    """Remove running headers/footers: edge lines that repeat on at least half the pages.

    Municipal minutes repeat a block such as "Protokoll nr 3 / Sammanträdesdatum / Göteborgs Stad
    kommunfullmäktige protokoll 17 (74)" at the top of every page. Left in, it ends up in every chunk,
    drowns the real content in the embedding and makes pages match on words like "Protokoll".
    Page numbers stay as metadata on each chunk, so nothing needed for citations is lost.
    """
    if len(pages) < MIN_PAGES:
        return pages

    lines_per_page = [page.text.splitlines() for page in pages]

    seen_on_pages: Counter[str] = Counter()
    for page, lines in zip(pages, lines_per_page, strict=True):
        edge = _edge_indexes(lines)
        keys: set[str] = set()
        for i, ln in enumerate(lines):
            if i in edge and ln.strip():
                keys |= _line_keys(ln, page.page)
        seen_on_pages.update(keys)

    limit = max(3, math.ceil(threshold * len(pages)))
    repeated = {key for key, count in seen_on_pages.items() if count >= limit}
    if not repeated:
        return pages

    stripped: list[PageText] = []
    for page, lines in zip(pages, lines_per_page, strict=True):
        edge = _edge_indexes(lines)
        kept = [ln for i, ln in enumerate(lines) if not (i in edge and _line_keys(ln, page.page) & repeated)]
        text = "\n".join(kept).strip()
        if text:
            stripped.append(PageText(page.page, text))

    # Never turn a document into nothing: if everything looked like a header, keep the original.
    return stripped or pages
