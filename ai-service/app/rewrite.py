"""Rewrites a manager's everyday wording into the terms the agreements and laws use, before the search.

"Får jag sparka någon som varit sjuk länge?" shares no words with the texts that answer it ("uppsägning", "saklig grund",
"sjukdom"), and an embedding of the first does not land near an embedding of those. The model is asked for a short search
phrase; the search then uses both the question and the phrase. A failed call means no rewrite, never a failed question."""
from app.llm import LlmClient, LlmUnavailableError

SYSTEM = (
    "Du hjälper en sökfunktion i svenska kollektivavtal och lagar för arbetsgivare i offentlig sektor: AB (Allmänna "
    "bestämmelser), LAS (lagen om anställningsskydd), MBL (medbestämmandelagen), semesterlagen, sjuklönelagen, "
    "föräldraledighetslagen, arbetstidslagen, arbetsmiljölagen, diskrimineringslagen och LOA (lagen om offentlig anställning). "
    "Skriv om användarens fråga till en kort sökfras med de facktermer och lagnamn som texterna använder. "
    "Vardagsord och facktermer: sparka/avskeda = uppsägning, avsked, saklig grund; sjukt barn = tillfällig föräldrapenning, "
    "vård av barn; gå ner i tid = sysselsättningsgrad, förkortning av arbetstid; karensdag = karensavdrag; ob = obekväm "
    "arbetstid, O-tillägg; timanställd = allmän visstidsanställning; fast anställd = tillsvidareanställning; skicka hem = "
    "avstängning; förtur = företrädesrätt; extra betalt = ersättning, tillägg; ledig = ledighet. "
    "Svara bara med sökfrasen, högst 25 ord, utan förklaring och utan punkt."
)


def rewrite(llm: LlmClient, question: str) -> str:
    """A short search phrase in the texts' own terms, or "" when the model cannot be reached or says nothing useful."""
    try:
        phrase = llm.generate(SYSTEM, question).strip().strip('"').splitlines()[0].strip()
    except (LlmUnavailableError, IndexError):
        return ""
    return phrase[:200] if phrase and phrase.lower() != question.lower() else ""


CONDENSE_SYSTEM = (
    "Du får en konversation mellan en chef och en assistent om svenska kollektivavtal och lagar, och en ny fråga eller ett "
    "kort svar från chefen. Skriv om den nya frågan så att den går att förstå helt utan konversationen: ta med ämnet och "
    "de uppgifter chefen gett tidigare när den nya frågan bygger på dem (till exempel 'Och för en 45-åring?' eller 'Ja, "
    "kommun'). Om den nya frågan redan är fristående, skriv den oförändrad. Svara bara med frågan."
)


def condense(llm: LlmClient, history: list[tuple[str, str]], question: str) -> str:
    """The question as a standalone one, using the last turns; "" when it could not be done (the question is then used as is)."""
    if not history:
        return ""
    turns = "\n\n".join(f"Chef: {q}\nAssistent: {a[:700]}" for q, a in history[-3:])
    try:
        text = llm.generate(CONDENSE_SYSTEM, f"Konversation:\n\n{turns}\n\nNy fråga: {question}").strip().strip('"').splitlines()[0].strip()
    except (LlmUnavailableError, IndexError):
        return ""
    return text[:500]
