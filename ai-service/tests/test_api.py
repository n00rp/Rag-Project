import uuid

from app.rag import NO_SUPPORT_ANSWER
from tests.conftest import make_pdf

SCHOOL = (
    "Barn- och utbildningsnämnden beslutade att införa ny skolskjuts för elever i "
    "Björkby. Beslutet gäller från höstterminen och omfattar buss och taxi."
)
CULTURE = "Kulturnämnden fördelade bidrag till föreningar för sommarens teaterfestival och konserter."


def ingest(client, owner, pages) -> str:
    doc_id = str(uuid.uuid4())
    r = client.post(
        "/ingest",
        data={"owner_id": owner, "document_id": doc_id},
        files={"file": ("protokoll.pdf", make_pdf(pages), "application/pdf")},
    )
    assert r.status_code == 200, r.text
    return doc_id


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_ingest_then_query_returns_answer_with_page_source(client, owner):
    doc_id = ingest(client, owner, [CULTURE, SCHOOL])

    r = client.post("/query", json={"owner_id": owner, "question": "Vad beslutades om skolskjuts i Björkby?"})

    assert r.status_code == 200
    body = r.json()
    assert body["grounded"] is True
    top = body["sources"][0]
    assert top["document_id"] == doc_id
    assert top["page"] == 2
    assert "skolskjuts" in top["snippet"]


def test_owner_cannot_see_other_owners_chunks(client, owner):
    ingest(client, owner, [SCHOOL])

    r = client.post(
        "/query", json={"owner_id": f"other-{uuid.uuid4()}", "question": "Vad beslutades om skolskjuts?"}
    )

    body = r.json()
    assert body["sources"] == []
    assert body["grounded"] is False
    assert body["answer"] == NO_SUPPORT_ANSWER


def test_document_filter_limits_search(client, owner):
    ingest(client, owner, [SCHOOL])
    culture_id = ingest(client, owner, [CULTURE])

    r = client.post(
        "/query",
        json={"owner_id": owner, "question": "skolskjuts Björkby", "document_ids": [culture_id]},
    )

    assert {s["document_id"] for s in r.json()["sources"]} <= {culture_id}


def test_reingest_replaces_chunks(client, owner):
    doc_id = str(uuid.uuid4())
    for text in (SCHOOL, CULTURE):
        client.post(
            "/ingest",
            data={"owner_id": owner, "document_id": doc_id},
            files={"file": ("a.pdf", make_pdf([text]), "application/pdf")},
        )

    r = client.post("/query", json={"owner_id": owner, "question": "skolskjuts", "top_k": 20})

    snippets = " ".join(s["snippet"] for s in r.json()["sources"])
    assert "skolskjuts" not in snippets


def test_delete_removes_document(client, owner):
    doc_id = ingest(client, owner, [SCHOOL])

    deleted = client.delete(f"/documents/{doc_id}", params={"owner_id": owner}).json()["deleted_chunks"]
    r = client.post("/query", json={"owner_id": owner, "question": "skolskjuts"})

    assert deleted >= 1
    assert r.json()["sources"] == []


def test_non_pdf_upload_is_400(client, owner):
    r = client.post(
        "/ingest",
        data={"owner_id": owner, "document_id": str(uuid.uuid4())},
        files={"file": ("x.pdf", b"hello", "application/pdf")},
    )
    assert r.status_code == 400


def test_scanned_pdf_is_422_with_clear_message(client, owner):
    r = client.post(
        "/ingest",
        data={"owner_id": owner, "document_id": str(uuid.uuid4())},
        files={"file": ("scan.pdf", make_pdf([""]), "application/pdf")},
    )
    assert r.status_code == 422
    assert "skannad" in r.json()["detail"]


def test_every_chunk_carries_the_document_header_from_page_one(client, owner):
    ingest(client, owner, ["Protokoll 2025-04-09 Kommunstyrelsen", SCHOOL])

    top = client.post("/query", json={"owner_id": owner, "question": "skolskjuts Björkby"}).json()["sources"][0]

    assert top["page"] == 2
    assert top["snippet"].startswith("Protokoll 2025-04-09 Kommunstyrelsen. ")


def test_min_score_refuses_when_nothing_is_similar_enough(client, owner):
    from app.config import Settings, get_settings
    from app.main import app

    ingest(client, owner, [SCHOOL])
    app.dependency_overrides[get_settings] = lambda: Settings(min_score=0.999)
    try:
        body = client.post("/query", json={"owner_id": owner, "question": "Hur mår kulturnämnden?"}).json()
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert body["answer"] == NO_SUPPORT_ANSWER
    assert body["grounded"] is False and body["sources"] == []


def test_min_score_looks_at_the_best_hit_only(monkeypatch):
    from app import rag
    from app.config import Settings
    from app.db import Hit
    from app.embeddings import FakeEmbedder
    from app.llm import FakeLlm

    hits = [Hit(uuid.uuid4(), 3, 0, "bäst", 0.90), Hit(uuid.uuid4(), 36, 1, "nästbäst", 0.70)]
    monkeypatch.setattr(rag.db, "search", lambda *a, **k: hits)
    answer = rag.answer_question(pool=None, embedder=FakeEmbedder(), llm=FakeLlm(), settings=Settings(min_score=0.8),
                                 owner_id="o", question="fråga")

    assert answer.grounded and [h.page for h in answer.sources] == [3, 36]
