import json
import uuid

import pytest

from app import rag
from app.config import Settings
from app.db import Hit
from app.main import app
from app.rag import NO_SUPPORT_ANSWER, Retrieval
from tests.test_api import SCHOOL, ingest


class Scripted:
    """A model that answers with the given pieces, one token each."""

    def __init__(self, *pieces):
        self.pieces = pieces
        self.closed = False
        self.system = None

    def generate(self, system, user):
        self.system = system
        return "".join(self.pieces)

    def stream(self, system, user):
        self.system = system
        try:
            yield from self.pieces
        finally:
            self.closed = True


HITS = [Hit(uuid.uuid4(), 1, 0, "text", 0.9)]
FOUND = Retrieval("fråga", HITS, refused=False)


def run(llm, structured=True, retrieval=FOUND):
    return list(rag.stream_answer(llm, retrieval, structured))


@pytest.mark.parametrize(
    ("text", "level", "body"),
    [
        ("STÖD: fullt\n\nSvaret [1].", "fullt", "Svaret [1]."),
        ("STÖD: delvis\n\nDet saknas en summa.", "delvis", "Det saknas en summa."),
        ("stöd: Delvis (summan saknas)\nSvar", "delvis", "Svar"),
        ("STÖD: inget\n\nJag hittar inget stöd för det i dokumenten.", "inget", "Jag hittar inget stöd för det i dokumenten."),
        ("Ett svar utan rad.", "fullt", "Ett svar utan rad."),
        (NO_SUPPORT_ANSWER, "inget", NO_SUPPORT_ANSWER),
    ],
)
def test_parse_support(text, level, body):
    assert rag.parse_support(text) == (level, body)


def test_structured_stream_reports_the_support_before_the_text_and_hides_the_line():
    events = run(Scripted("STÖD", ": del", "vis\n", "\nDet saknas ", "en summa ", "[1]."))

    kinds = [k for k, _ in events]
    assert kinds[:2] == ["sources", "support"] and kinds[-1] == "done"
    assert events[1] == ("support", "delvis")
    assert "".join(p for k, p in events if k == "token") == "\nDet saknas en summa [1]."
    answer = events[-1][1]
    assert (answer.answer, answer.support, answer.grounded) == ("Det saknas en summa [1].", "delvis", True)


def test_a_model_that_ignores_the_format_is_treated_as_an_ordinary_answer():
    events = run(Scripted("Ett helt vanligt svar utan någon särskild rad, ", "som fortsätter en bra stund [1]."))

    assert ("support", "fullt") in events
    assert "".join(p for k, p in events if k == "token").startswith("Ett helt vanligt svar")
    assert events[-1][1].support == "fullt"


def test_stop_asking_the_model_as_soon_as_it_says_there_is_no_support():
    llm = Scripted("STÖD: inget\n", "\nJag hittar ", "inget stöd för det i dokumenten.", " och sen mycket mer text")

    events = run(llm)

    assert [k for k, _ in events] == ["sources", "done"]  # no tokens shown
    answer = events[-1][1]
    assert (answer.answer, answer.grounded, answer.sources, answer.support) == (NO_SUPPORT_ANSWER, False, [], "inget")
    assert llm.closed  # the generation was cancelled


def test_a_very_short_answer_is_not_lost():
    events = run(Scripted("STÖD: fullt"))

    assert events[-1][1].support == "fullt"
    assert events[-1][1].grounded is True


def test_without_structured_mode_the_stream_is_unchanged():
    events = run(Scripted("Svar ", "här."), structured=False)

    assert [k for k, _ in events] == ["sources", "token", "token", "done"]


@pytest.mark.parametrize("question", [
    "Sammanfatta kommunstyrelsens sammanträde 2025-04-09.",
    "Hur många yrkanden avslogs?",
    "Lista alla yrkanden från SD som avslogs.",
    "Vad är skillnaden mellan A och B?",
    "Ge en överblick över besluten.",
])
def test_overview_questions_are_recognised(question):
    assert rag.BROAD.search(question)


@pytest.mark.parametrize("question", ["Vad beslutades om skolskjuts?", "Vem anmälde jäv?", "Hur stor var budgeten?", "Hur många röstade ja och nej?", "Hur många planeter finns det?"])
def test_ordinary_questions_are_not_overview_questions(question):
    assert not rag.BROAD.search(question)


def test_overview_questions_get_more_excerpts_and_a_warning_in_the_prompt(client, owner):
    ingest(client, owner, [SCHOOL] * 15)
    settings = Settings(min_score=0, top_k=3, broad_top_k=7)
    args = dict(pool=app.state.pool, embedder=app.state.embedder, settings=settings, owner_id=owner)

    ordinary = rag.retrieve(question="Vad beslutades om skolskjuts?", **args)
    overview = rag.retrieve(question="Sammanfatta besluten om skolskjuts.", **args)

    assert (len(ordinary.hits), ordinary.broad) == (3, False)
    assert (len(overview.hits), overview.broad) == (7, True)
    assert "kan vara ofullständig" in rag.system_prompt(structured=False, broad=True)
    assert "kan vara ofullständig" not in rag.system_prompt(structured=False, broad=False)


def test_the_query_endpoint_reports_support_and_overview(client, owner):
    ingest(client, owner, [SCHOOL])

    body = client.post("/query", json={"owner_id": owner, "question": "Sammanfatta skolskjuts"}).json()

    assert body["support"] == "fullt" and body["broad"] is True


def test_stream_events_carry_support_and_overview_in_done(client, owner):
    ingest(client, owner, [SCHOOL])

    with client.stream("POST", "/query/stream", json={"owner_id": owner, "question": "Sammanfatta skolskjuts"}) as r:
        done = [json.loads(line) for line in r.iter_lines() if line][-1]

    assert (done["support"], done["broad"]) == ("fullt", True)
