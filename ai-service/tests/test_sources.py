from uuid import uuid4

from app.sources import named_documents

SJLL, LAS, AB, AB_KOMM, MBL = (uuid4() for _ in range(5))
HEADERS = {
    SJLL: "Förkortning: SjLL Lag (1991:1047) om sjuklön SFS nr: 1991:1047",
    LAS: "Förkortning: LAS Lag (1982:80) om anställningsskydd SFS nr: 1982:80",
    MBL: "Förkortning: MBL Lag (1976:580) om medbestämmande i arbetslivet",
    AB: "AB 25 Allmänna bestämmelser I LYDELSE 2025-04-01",
    AB_KOMM: "Kommentarer till AB 25 Allmänna bestämmelser",
}


def test_a_law_is_named_by_its_title_word_or_its_abbreviation():
    assert named_documents("Hur mycket får man enligt sjuklönelagen?", HEADERS) == [SJLL]
    assert named_documents("Vad säger LAS om turordning?", HEADERS) == [LAS]
    assert named_documents("Vad säger lagen om medbestämmande?", HEADERS) == [MBL]


def test_an_abbreviation_must_be_in_capitals_and_everyday_words_name_nothing():
    assert named_documents("las du lagen i går? ab och till", HEADERS) == []
    assert named_documents("Hur lång uppsägningstid har man?", HEADERS) == []


def test_a_word_shared_by_many_headers_names_none():
    shared = {uuid4(): f"Protokoll Kommunstyrelsen {n}" for n in range(4)}
    assert named_documents("Vad beslutade kommunstyrelsen?", shared) == []
