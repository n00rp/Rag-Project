from app.rag import topics


def test_a_list_of_three_or_more_things_is_split_into_topics():
    assert topics("provanställning, uppsägningstid (62-åring) och semesterdagar vid 45 år?") == [
        "provanställning", "uppsägningstid (62-åring)", "semesterdagar vid 45 år"]


def test_an_ordinary_question_is_left_alone():
    assert topics("Hur lång uppsägningstid har en arbetstagare själv?") == []
    assert topics("Vad är skillnaden mellan AB och LAS?") == []
    assert topics("Hur länge får en provanställning vara, och vad händer sedan?") == []  # only two parts


def test_a_sentence_with_a_few_clauses_is_not_a_list():
    assert topics("Hur lång tid före ledighetens början ska den anmälas, enligt AB och enligt lagen?") == []


def test_an_overview_that_misses_one_point_is_still_an_answer_but_a_plain_refusal_is_not():
    from app.db import Hit
    from app.rag import NO_SUPPORT_ANSWER, _finish

    hits = [Hit.__new__(Hit)]
    overview = "**Provanställning:** högst 6 kalendermånader [1]. " * 6 + f"**Jour:** {NO_SUPPORT_ANSWER}"
    assert _finish(overview, hits, broad=True).grounded
    assert not _finish(overview, hits, broad=False).grounded  # an ordinary answer containing the sentence is a refusal
    assert not _finish(NO_SUPPORT_ANSWER, hits, broad=True).grounded
