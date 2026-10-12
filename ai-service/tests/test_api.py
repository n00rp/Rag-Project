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
