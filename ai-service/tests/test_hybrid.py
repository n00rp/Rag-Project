import uuid

import pytest

from app import db, rag
from app.config import Settings
from app.db import Hit
from app.main import app
from tests.test_api import ingest

CASE = "Protokoll nr 8 Sammanträdesdatum: 2025-04-09 Kommunstyrelsen\n§ 317 Ärendenummer SLK-2025-00392 Yrkande om försvarsindustri avslås."
OTHER = "Protokoll nr 3 Sammanträdesdatum: 2024-03-21 Kommunfullmäktige\n§ 108 Ärendenummer SLK-2024-00256 Kapitaltillskott till Liseberg."
FILLER = ["Sida med helt andra ord om skolskjuts och bussar i Björkby.", "Sida om kulturnämndens bidrag till teaterfestivalen."]


def retrieve(owner, question, **settings):
    return rag.retrieve(pool=app.state.pool, embedder=app.state.embedder, settings=Settings(min_score=0, **settings),
                        owner_id=owner, question=question)


def test_keyword_search_finds_a_case_number_that_similarity_alone_misses(client, owner):
    ingest(client, owner, [FILLER[0], CASE, FILLER[1]])
    question = "Vad gäller ärende SLK-2025-00392?"
    embedding = app.state.embedder.embed_query(question)

    hits = db.search_hybrid(app.state.pool, owner, embedding, question, 3, max_df=0.5)

    assert "SLK-2025-00392" in hits[0].content
    assert hits[0].matched


def test_the_keyword_side_only_uses_rare_words(client, owner):
    """With the default threshold (1 % of the chunks) a corpus this small has no rare words: plain vector search."""
    ingest(client, owner, [FILLER[0], CASE, FILLER[1]])
    question = "Vad gäller ärende SLK-2025-00392?"

    hits = db.search_hybrid(app.state.pool, owner, app.state.embedder.embed_query(question), question, 3)

    assert not any(h.matched for h in hits)


def test_only_questions_with_a_case_or_section_number_use_the_keyword_search(client, owner, monkeypatch):
    ingest(client, owner, [CASE])
    calls = []
    real = db.search_hybrid
    monkeypatch.setattr(rag.db, "search_hybrid", lambda *a, **k: calls.append("hybrid") or real(*a, **k))

    retrieve(owner, "Vad gäller ärende SLK-2025-00392?")
    retrieve(owner, "Vad behandlades under § 317?")
    retrieve(owner, "Vad beslutades om försvarsindustri?")
    retrieve(owner, "Vad gäller ärende SLK-2025-00392?", hybrid_identifiers=False)

    assert calls == ["hybrid", "hybrid"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [("SLK-2025-00392", True), ("slk-2025-00392", True), ("§ 317", True), ("§317", True), ("avsnitt 317", False), ("2025-04-09", False)],
)
def test_identifier_patterns(text, expected):
    assert bool(rag.IDENTIFIER.search(f"Vad gäller {text}?")) is expected


def test_a_date_in_the_question_limits_the_search_to_that_meeting(client, owner):
    ingest(client, owner, [CASE])
    ingest(client, owner, [OTHER])

    only_april = retrieve(owner, "Vad behandlades vid sammanträdet 2025-04-09?")
    only_march = retrieve(owner, "Vad behandlades vid sammanträdet 2024-03-21?")

    assert {"Sammanträdesdatum: 2025-04-09" in h.content for h in only_april.hits} == {True}
    assert {"Sammanträdesdatum: 2024-03-21" in h.content for h in only_march.hits} == {True}


def test_an_unknown_date_falls_back_to_searching_everything(client, owner):
    ingest(client, owner, [CASE])

    result = retrieve(owner, "Vad hände den 1999-01-01?")

    assert result.hits  # nothing carries that date, so the filter is dropped instead of returning nothing


def test_date_filter_can_be_turned_off(client, owner):
    ingest(client, owner, [CASE])
    ingest(client, owner, [OTHER])

    result = retrieve(owner, "Vad behandlades vid sammanträdet 2025-04-09?", filter_by_date=False)

    assert len({h.document_id for h in result.hits}) == 2


def test_a_hit_found_by_a_rare_word_is_not_refused_for_low_similarity(monkeypatch):
    hits = [Hit(uuid.uuid4(), 1, 0, "text", 0.5, matched=True)]
    monkeypatch.setattr(rag.db, "search", lambda *a, **k: hits)
    monkeypatch.setattr(rag.db, "search_hybrid", lambda *a, **k: hits)
    monkeypatch.setattr(rag.db, "contains_any", lambda *a, **k: True)  # the numbers exist; this test is about similarity
    settings = Settings(min_score=0.83)
    args = dict(pool=None, embedder=app.state.embedder, settings=settings, owner_id="o")

    assert rag.retrieve(question="Vad gäller ärende SLK-2025-00392?", **args).refused is False
    weak = [Hit(uuid.uuid4(), 1, 0, "text", 0.5)]
    monkeypatch.setattr(rag.db, "search_hybrid", lambda *a, **k: weak)
    assert rag.retrieve(question="Vad gäller ärende SLK-2099-99999?", **args).refused is True


def test_a_case_or_section_number_that_is_in_no_document_is_refused_outright(client, owner):
    ingest(client, owner, [CASE])

    assert retrieve(owner, "Vad gäller ärende SLK-2030-00001?").refused
    assert retrieve(owner, "Vad behandlades under § 9999?").refused
    assert retrieve(owner, "Vad behandlades under § 9999 vid sammanträdet 2025-04-09?").refused


def test_a_known_case_or_section_number_is_not_refused(client, owner):
    ingest(client, owner, [CASE])

    assert not retrieve(owner, "Vad gäller ärende SLK-2025-00392?").refused
    assert not retrieve(owner, "Vad behandlades under § 317?").refused
    assert not retrieve(owner, "Vad behandlades under §317?").refused
    assert retrieve(owner, "Vad behandlades under § 31?").refused  # 31 is not the start of 317


def test_the_check_belongs_to_the_owner(client, owner):
    ingest(client, owner, [CASE])

    assert retrieve("someone-else", "Vad gäller ärende SLK-2025-00392?").refused


def test_neighbouring_chunks_can_be_given_to_the_model_without_changing_the_sources(client, owner):
    long_page = " ".join(f"Mening nummer {i} i protokollet om skolskjuts." for i in range(60))
    ingest(client, owner, [long_page])

    plain = retrieve(owner, "Mening nummer 3 skolskjuts")
    wide = retrieve(owner, "Mening nummer 3 skolskjuts", context_neighbors=1)

    assert [h.content for h in plain.hits] == [h.content for h in wide.hits]  # what the user sees is unchanged
    assert all(h.context is None for h in plain.hits)
    assert all(h.context and len(h.context) > len(h.content) for h in wide.hits)
    assert rag.build_user_prompt("fråga", wide.hits).count("Mening") > rag.build_user_prompt("fråga", plain.hits).count("Mening")
