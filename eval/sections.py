"""Splits the protocols into their sections (§) with page span, title, decision and full text.

Used by the eval to build and verify questions: every expected answer is a (file, §) pair, and the pages
that count as correct are derived from here. Run directly to look at what was found:

    ai-service/.venv/Scripts/python eval/sections.py KS_protokoll_20250409.pdf 317
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ai-service"))

from app.pdf import extract_pages  # noqa: E402

START = re.compile(r"^§ ?(\d+) Ärendenummer (\S+)[ \t]*$", re.M)
TITLE_END = re.compile(r"^(Beslut|Ärendet|Förslag|Bakgrund|Tidigare behandling|Handlingar)\b", re.M)
NEXT_HEADING = re.compile(
    r"\n(Tidigare behandling|Handlingar|Yrkanden|Ärendet|Förslag till beslut|Bakgrund|Ställningstagande|Propositionsordning|"
    r"Protokollsanteckning|Protokollsanteckningar|Omröstning|Jäv|Sammanfattning|Expedieras|Justering)\b"
)


@dataclass(frozen=True)
class Section:
    file: str
    number: int
    case_number: str
    first_page: int
    last_page: int
    title: str
    decision: str
    text: str

    @property
    def pages(self) -> range:
        return range(self.first_page, self.last_page + 1)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def load_sections(pdf_dir: Path) -> list[Section]:
    sections: list[Section] = []
    for pdf in sorted(pdf_dir.glob("*.pdf")):
        pages = extract_pages(pdf.read_bytes())
        starts = []  # (page index, match)
        for i, page in enumerate(pages):
            m = START.search(page.text)
            if m:
                starts.append((i, m))
        for k, (i, m) in enumerate(starts):
            end = max(starts[k + 1][0] - 1 if k + 1 < len(starts) else len(pages) - 1, i)
            text = "\n".join(p.text for p in pages[i : end + 1])
            rest = text[text.index(m.group(0)) + len(m.group(0)) :].lstrip("\n")
            stop = TITLE_END.search(rest)
            title_block = rest[: stop.start()] if stop and stop.start() < 600 else "\n".join(rest.split("\n")[:3])
            decision = ""
            if stop and stop.group(1) == "Beslut":
                after = rest[stop.end() :]
                cut = NEXT_HEADING.search(after)
                decision = _clean(after[: cut.start()] if cut else after)
            sections.append(
                Section(pdf.name, int(m.group(1)), m.group(2), pages[i].page, pages[end].page,
                        _clean(title_block), decision, text)
            )
    return sections


if __name__ == "__main__":
    found = load_sections(ROOT / "data" / "goteborg")
    if len(sys.argv) >= 3:
        for s in found:
            if s.file == sys.argv[1] and s.number == int(sys.argv[2]):
                print(f"{s.file} § {s.number} ({s.case_number}) s.{s.first_page}-{s.last_page}")
                print(f"{s.title}\n--\n{s.decision}\n==\n{s.text[:1500]}")
    else:
        print(len(found), "sections")
        for s in found[:5]:
            print(f"{s.file} § {s.number} s.{s.first_page}-{s.last_page} | {s.title[:70]} | {s.decision[:80]}")
