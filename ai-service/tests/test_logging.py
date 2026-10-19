import json
import logging

import pytest

from app.logging_setup import JsonFormatter, trace_id_from, trace_id_var
from tests.test_api import SCHOOL, ingest

TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"
PARENT = f"00-{TRACE}-00f067aa0ba902b7-01"


@pytest.mark.parametrize(
    ("header", "expected"),
    [(PARENT, TRACE), (PARENT.upper(), TRACE), ("", None), (None, None), ("garbage", None), (f"00-{TRACE}-short-01", None)],
)
def test_trace_id_from_a_traceparent_header(header, expected):
    assert trace_id_from(header) == expected


def test_log_lines_are_json_with_the_trace_id_and_extra_fields():
    token = trace_id_var.set(TRACE)
    try:
        record = logging.LogRecord("ai-service", logging.INFO, __file__, 1, "answer", (), None)
        record.total_ms = 123
        line = json.loads(JsonFormatter().format(record))
    finally:
        trace_id_var.reset(token)

    assert (line["msg"], line["level"], line["trace_id"], line["total_ms"]) == ("answer", "info", TRACE, 123)
    assert line["ts"].endswith("Z")


def test_the_trace_id_from_the_api_is_returned_and_used(client):
    r = client.get("/health", headers={"traceparent": PARENT})

    assert r.headers["x-trace-id"] == TRACE


def test_a_request_without_a_trace_id_gets_one(client):
    r = client.get("/health")

    assert len(r.headers["x-trace-id"]) == 32


def test_an_answer_logs_its_timings_but_never_the_question(client, owner, caplog):
    ingest(client, owner, [SCHOOL])
    question = "En mycket särskild fråga om skolskjuts i Björkby"

    with caplog.at_level(logging.INFO, logger="ai-service"):
        with client.stream("POST", "/query/stream", json={"owner_id": owner, "question": question},
                           headers={"traceparent": PARENT}) as r:
            list(r.iter_lines())

    answer = next(rec for rec in caplog.records if rec.getMessage() == "answer")
    assert answer.mode == "stream" and answer.question_chars == len(question)
    assert answer.retrieve_ms >= 0 and answer.first_token_ms >= answer.retrieve_ms and answer.total_ms >= answer.first_token_ms
    assert answer.tokens > 0
    assert all(question not in json.dumps(vars(rec), default=str) for rec in caplog.records)
