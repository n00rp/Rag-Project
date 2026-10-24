from app.rewrite import condense


class Llm:
    def __init__(self, reply: str) -> None:
        self.reply, self.prompts = reply, []

    def generate(self, system: str, user: str) -> str:
        self.prompts.append(user)
        return self.reply


def test_a_follow_up_is_made_standalone_from_the_last_turns():
    llm = Llm("Hur många semesterdagar har en 45-åring?\nextra rad som ignoreras")
    out = condense(llm, [("Hur många semesterdagar har en 35-åring?", "25 dagar [1]")], "Och för en 45-åring?")
    assert out == "Hur många semesterdagar har en 45-åring?"
    assert "Chef: Hur många semesterdagar har en 35-åring?" in llm.prompts[0] and "Ny fråga: Och för en 45-åring?" in llm.prompts[0]


def test_the_model_is_not_asked_when_there_is_no_conversation():
    llm = Llm("onödigt")
    assert condense(llm, [], "Hur lång är provanställningen?") == ""
    assert llm.prompts == []
