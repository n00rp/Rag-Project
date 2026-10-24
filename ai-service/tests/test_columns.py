from app.columns import column_text


def word(text, x0, top):
    return {"text": text, "x0": x0, "x1": x0 + 6 * len(text), "top": top}


def test_a_two_column_block_is_read_column_by_column_and_full_width_lines_stay_in_place():
    words = [word("Intro", 50, 0), word("text", 100, 0)]
    for row in range(1, 13):  # a left column of wrapped lines next to a shorter right column
        words += [word(f"v{row}a", 50, row * 12), word("vänster", 100, row * 12), word("kolumn", 160, row * 12)]
        if row <= 5:
            words += [word(f"h{row}{n}", 320 + n * 40, row * 12) for n in range(6)]
    words += [word("Mom.", 50, 200), word("2", 90, 200), word("Fortsättning", 100, 200), word("hela", 190, 200),
              word("sidan", 230, 200), word("och", 270, 200), word("vidare", 296, 200), word("till", 340, 200)]

    lines = column_text(words, width=600).splitlines()
    assert lines[0] == "Intro text"
    assert lines[1:13] == [f"v{n}a vänster kolumn" for n in range(1, 13)]  # the whole left column first
    assert lines[13] == "h10 h11 h12 h13 h14 h15"  # then the right one
    assert lines[-1] == "Mom. 2 Fortsättning hela sidan och vidare till"


def test_a_table_read_row_by_row_is_left_alone():
    words = []
    for row in range(1, 8):
        words += [word(f"term{row}", 50, row * 12), word("betyder", 320, row * 12), word(f"sak{row}", 380, row * 12)]
    assert column_text(words, width=600) is None


def test_pages_without_a_gutter_are_left_to_the_normal_extraction():
    words = [word("Bara", 50, 0), word("en", 90, 0), word("kolumn", 110, 0), word("text", 50, 12), word("till", 90, 12)]
    assert column_text(words, width=600) is None
