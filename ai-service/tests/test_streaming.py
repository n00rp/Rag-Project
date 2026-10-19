import json

import httpx
import pytest

from app import llm as llm_module
from app.config import Settings, get_settings
from app.llm import LlmUnavailableError, OllamaLlm
from app.main import app
from app.rag import NO_SUPPORT_ANSWER
from tests.test_api import SCHOOL, ingest


def read_events(client, owner, question) -> list[dict]:
    with client.stream("POST", "/query/stream", json={"owner_id": owner, "question": question}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/x-ndjson")
        return [json.loads(line) for line in r.iter_lines() if line]


def test_stream_sends_sources_first_then_tokens_then_the_whole_answer(client, owner):
    ingest(client, owner, ["Protokoll 2025-04-09 Kommunstyrelsen", SCHOOL])

    events = read_events(client, owner, "skolskjuts Björkby")

    kinds = [e["type"] for e in events]
    assert kinds[0] == "sources" and kinds[-1] == "done"
    assert set(kinds[1:-1]) == {"token"} and len(kinds) > 3
    assert events[0]["sources"][0]["snippet"].startswith("Barn- och utbildningsnämnden")  # header not shown
    done = events[-1]
    assert done["grounded"] is True
    assert "".join(e["text"] for e in events if e["type"] == "token").strip() == done["answer"]
    assert "Protokoll 2025-04-09 Kommunstyrelsen" in done["answer"]  # the fake LLM echoes its context


def test_stream_matches_the_non_streaming_answer(client, owner):
    ingest(client, owner, [SCHOOL])
    plain = client.post("/query", json={"owner_id": owner, "question": "skolskjuts Björkby"}).json()

    done = read_events(client, owner, "skolskjuts Björkby")[-1]

    assert done["answer"] == plain["answer"]


def test_stream_refusal_is_a_single_done_event(client, owner):
    ingest(client, owner, [SCHOOL])
    app.dependency_overrides[get_settings] = lambda: Settings(min_score=0.999)
    try:
        events = read_events(client, owner, "Hur mår kulturnämnden?")
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert events == [{"type": "done", "answer": NO_SUPPORT_ANSWER, "grounded": False, "support": "inget", "broad": False}]


def test_stream_reports_an_unreachable_model_as_an_error_event(client, owner, monkeypatch):
    ingest(client, owner, [SCHOOL])

    class Down:
        def stream(self, system, user):
            raise LlmUnavailableError("nere")
            yield  # makes this a generator

    monkeypatch.setattr(app.state, "llm", Down())

    events = read_events(client, owner, "skolskjuts")

    assert events[-1]["type"] == "error" and events[-1]["code"] == "ai_unavailable"


def test_other_owners_cannot_stream_each_others_chunks(client, owner):
    ingest(client, owner, [SCHOOL])

    events = read_events(client, "someone-else", "skolskjuts Björkby")

    assert events == [{"type": "done", "answer": NO_SUPPORT_ANSWER, "grounded": False, "support": "inget", "broad": False}]


def ollama_with(handler):
    """An OllamaLlm whose HTTP calls go to `handler` instead of the network."""
    def fake_stream(method, url, **kwargs):
        kwargs.pop("timeout", None)
        return httpx.Client(transport=httpx.MockTransport(handler)).stream(method, url, **kwargs)

    return OllamaLlm("http://ollama.test", "m", 5), fake_stream


def sse(*chunks) -> bytes:
    lines = [f"data: {json.dumps({'choices': [{'delta': {'content': c}}]})}" for c in chunks]
    return ("\n\n".join(lines) + "\n\ndata: [DONE]\n\n").encode()


def test_ollama_stream_yields_the_content_deltas(monkeypatch):
    client, fake = ollama_with(lambda req: httpx.Response(200, content=sse("Hej ", "där", "", None)))
    monkeypatch.setattr(llm_module.httpx, "stream", fake)

    assert list(client.stream("s", "u")) == ["Hej ", "där"]


@pytest.mark.parametrize("failure", [httpx.ConnectError("nere"), httpx.ReadTimeout("segt")])
def test_ollama_stream_turns_connection_problems_into_unavailable(monkeypatch, failure):
    def handler(request):
        raise failure

    client, fake = ollama_with(handler)
    monkeypatch.setattr(llm_module.httpx, "stream", fake)

    with pytest.raises(LlmUnavailableError):
        list(client.stream("s", "u"))


def test_ollama_stream_turns_an_error_status_into_unavailable(monkeypatch):
    client, fake = ollama_with(lambda req: httpx.Response(503, content=b"busy"))
    monkeypatch.setattr(llm_module.httpx, "stream", fake)

    with pytest.raises(LlmUnavailableError, match="503"):
        list(client.stream("s", "u"))
