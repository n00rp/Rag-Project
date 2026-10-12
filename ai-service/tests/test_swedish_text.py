"""Å, Ä and Ö must survive the whole pipeline, including the messy forms real PDFs produce."""

import os
import unicodedata
import uuid
from pathlib import Path

import pytest
from fpdf import FPDF

from app.chunking import chunk_pages
from app.pdf import PageText, extract_pages
from app.text import normalize_text

SWEDISH = "Östra Ängby: åk 1–6 får skolskjuts. Överenskommelse för älvdalen, ÅÄÖ åäö."

_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


def _font() -> str:
    for candidate in [os.environ.get("TEST_TTF_FONT", ""), *_FONT_CANDIDATES]:
        if candidate and Path(candidate).exists():
            return candidate
    pytest.skip("Inget TrueType-typsnitt hittades (sätt TEST_TTF_FONT)")


def embedded_font_pdf(text: str) -> bytes:
    """A PDF with an embedded TrueType font, i.e. how real documents are produced."""
    pdf = FPDF()
    pdf.add_font("Body", fname=_font())
    pdf.set_font("Body", size=12)
    pdf.add_page()
    pdf.multi_cell(0, 8, text)
    return bytes(pdf.output())


class TestNormalizeText:
    def test_composes_decomposed_accents(self):
        decomposed = unicodedata.normalize("NFD", "ÅÄÖåäö")
        assert len(decomposed) > 6
        assert normalize_text(decomposed) == "ÅÄÖåäö"

    def test_leaves_already_composed_swedish_untouched(self):
        assert normalize_text(SWEDISH) == SWEDISH

    def test_expands_ligatures(self):
        assert normalize_text("ﬁnansiering och ﬂexibilitet") == "finansiering och flexibilitet"

    def test_replaces_non_breaking_space_and_strips_nul(self):
        assert normalize_text("5\u00a0kr\x00") == "5 kr"


class TestPdfExtraction:
    def test_embedded_font_pdf_keeps_swedish_characters(self):
        pages = extract_pages(embedded_font_pdf(SWEDISH))
        assert pages[0].text == SWEDISH

    def test_decomposed_accents_in_pdf_come_out_composed(self):
        pages = extract_pages(embedded_font_pdf(unicodedata.normalize("NFD", SWEDISH)))
        assert pages[0].text == SWEDISH

    def test_ligatures_in_pdf_are_expanded(self):
        pages = extract_pages(embedded_font_pdf("Kommunens ﬁnansiering och ﬂexibla ﬁnanser sjunker."))
        assert "finansiering" in pages[0].text
        assert "ﬁ" not in pages[0].text


def test_chunking_never_splits_a_swedish_character():
    text = " ".join(["Förvaltningsövergripande ärenden åtgärdas"] * 80)
    chunks = chunk_pages([PageText(1, text)], size=120, overlap=30)
    assert all("\ufffd" not in c.text for c in chunks)
    assert {w for c in chunks for w in c.text.split()} == set(text.split())


class TestEndToEnd:
    @staticmethod
    def _ingest(client, owner, pdf: bytes, filename: str) -> str:
        doc_id = str(uuid.uuid4())
        r = client.post(
            "/ingest",
            data={"owner_id": owner, "document_id": doc_id},
            files={"file": (filename, pdf, "application/pdf")},
        )
        assert r.status_code == 200, r.text
        return doc_id

    def test_filename_with_swedish_characters_is_accepted(self, client, owner):
        self._ingest(client, owner, embedded_font_pdf(SWEDISH), "Östra Ängby – protokoll.pdf")

    def test_query_with_decomposed_accents_finds_composed_text(self, client, owner):
        self._ingest(client, owner, embedded_font_pdf("Överenskommelsen gäller älvdalen och omfattar alla skolor i kommunen."), "a.pdf")
        question = unicodedata.normalize("NFD", "Gäller överenskommelsen älvdalen?")

        body = client.post("/query", json={"owner_id": owner, "question": question}).json()

        assert body["grounded"] is True
        assert "älvdalen" in body["sources"][0]["snippet"]

    def test_uppercase_question_matches_lowercase_text(self, client, owner):
        self._ingest(client, owner, embedded_font_pdf("Skolskjuts i östra ängby beslutades av nämnden vid sammanträdet i mars."), "a.pdf")

        body = client.post(
            "/query", json={"owner_id": owner, "question": "SKOLSKJUTS I ÖSTRA ÄNGBY"}
        ).json()

        assert "östra ängby" in body["sources"][0]["snippet"]

    def test_ligature_pdf_is_searchable_by_plain_spelling(self, client, owner):
        self._ingest(client, owner, embedded_font_pdf("Budget för ﬁnansiering av skolan och förskolan nästa år."), "a.pdf")

        body = client.post(
            "/query", json={"owner_id": owner, "question": "finansiering av skolan"}
        ).json()

        assert "finansiering" in body["sources"][0]["snippet"]
