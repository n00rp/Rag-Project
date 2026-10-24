"""Which documents does a question name? "enligt LAS", "i semesterlagen", "sjuklönelagen" point at one law; the long AB
commentary that discusses the same subject should not crowd it out.

The register is the document header every chunk already starts with (title, abbreviation: "Förkortning: SjLL Lag
(1991:1047) om sjuklön"). A word names a document when it starts with one of the header's distinctive words (one that
only a few documents have), so "sjuklönelagen" matches "sjuklön". Short abbreviations (LAS, MBL, AB) must be written in
capitals, so that ordinary words do not match."""
import re
from collections import Counter
from uuid import UUID

_WORD = re.compile(r"[A-Za-zÅÄÖåäö]{3,}")
MAX_DOCUMENTS_PER_WORD = 3  # a header word shared by more documents ("bestämmelser", "kommunstyrelsen") names none of them
STOP = {"förkortning", "protokoll", "sammanträdesdatum", "lydelse", "allmänna", "bestämmelser", "lagen", "lag"}


def _header_words(header: str) -> set[str]:
    return {w for w in _WORD.findall(header) if w.lower() not in STOP}


def named_documents(text: str, headers: dict[UUID, str]) -> list[UUID]:
    """Documents whose header has a distinctive word that `text` uses (as a prefix of one of its own words)."""
    words = {w.lower() for w in _WORD.findall(text)}
    capitals = set(re.findall(r"\b[A-ZÅÄÖ]{2,6}\b", text))
    per_doc = {doc: _header_words(h) for doc, h in headers.items()}
    spread = Counter(w.lower() for ws in per_doc.values() for w in {x.lower() for x in ws})
    found = []
    for doc, ws in per_doc.items():
        for w in ws:
            low = w.lower()
            if len(w) <= 4:  # abbreviations: exact and in capitals
                if w in capitals and w.isupper():
                    found.append(doc)
                    break
            elif spread[low] <= MAX_DOCUMENTS_PER_WORD and any(t.startswith(low) for t in words):
                found.append(doc)
                break
    return found
