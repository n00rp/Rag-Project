import pytest

from app.chunking import add_header, chunk_pages, document_header, strip_header
from app.pdf import PageText


def test_chunks_keep_their_page_number():
    pages = [PageText(1, "Första sidan handlar om skolskjuts."), PageText(2, "Andra sidan om budget.")]
    chunks = chunk_pages(pages, size=500, overlap=50)
    assert [c.page for c in chunks] == [1, 2]
    assert [c.index for c in chunks] == [0, 1]


def test_long_page_is_split_and_respects_size():
    text = " ".join(f"Mening nummer {i} i protokollet." for i in range(200))
    chunks = chunk_pages([PageText(3, text)], size=300, overlap=60)
    assert len(chunks) > 5
    assert all(len(c.text) <= 300 + 60 for c in chunks)
    assert all(c.page == 3 for c in chunks)


def test_overlap_repeats_text_between_neighbours():
    text = " ".join(f"ord{i}" for i in range(300))
    chunks = chunk_pages([PageText(1, text)], size=200, overlap=50)
    assert set(chunks[0].text.split()[-3:]) & set(chunks[1].text.split()[:10])


def test_no_text_lost():
    words = [f"ord{i}" for i in range(500)]
    chunks = chunk_pages([PageText(1, " ".join(words))], size=200, overlap=40)
    seen = {w for c in chunks for w in c.text.split()}
    assert seen == set(words)


def test_overlap_must_be_smaller_than_size():
    with pytest.raises(ValueError):
        chunk_pages([PageText(1, "text")], size=100, overlap=100)


def test_document_header_uses_first_lines_of_first_page_only():
    pages = [
        PageText(1, "Protokoll nr 8\n\nSammanträdesdatum: 2025-04-09\nKommunstyrelsen\nBrödtext"),
        PageText(2, "Annan sida"),
    ]
    assert document_header(pages) == "Protokoll nr 8 Sammanträdesdatum: 2025-04-09 Kommunstyrelsen"
    assert document_header([]) == ""
    assert len(document_header([PageText(1, "x" * 500)])) == 200


def test_header_is_added_to_every_chunk_and_can_be_stripped_again():
    chunks = chunk_pages([PageText(1, "Första."), PageText(2, "Andra.")], size=500, overlap=50)
    with_header = add_header(chunks, "Protokoll 2025-04-09")
    assert [c.text for c in with_header] == ["Protokoll 2025-04-09\nFörsta.", "Protokoll 2025-04-09\nAndra."]
    assert [strip_header(c.text) for c in with_header] == ["Första.", "Andra."]
    assert add_header(chunks, "") == chunks
    assert strip_header("text utan rubrik") == "text utan rubrik"
