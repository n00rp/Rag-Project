from app.boilerplate import strip_repeated_lines
from app.pdf import PageText

TOPICS = ["skolskjuts", "budget", "kultur", "trafik", "parkering", "bibliotek", "simhall", "fritid"]


def minutes(n_pages: int) -> list[PageText]:
    """Pages with a 3-line running header and a body of 10 distinct lines each."""
    pages = []
    for n in range(1, n_pages + 1):
        topic = TOPICS[(n - 1) % len(TOPICS)]
        header = f"Protokoll nr 3\nSammanträdesdatum: 2024-03-21\nGöteborgs Stad protokoll {n} ({n_pages})\n"
        body = "\n".join(f"Rad {i} om {topic}: nämnden beslutade åtgärd {topic}{i}." for i in range(10))
        pages.append(PageText(n, header + body))
    return pages


def test_running_header_is_removed_but_content_and_page_numbers_stay():
    result = strip_repeated_lines(minutes(8))

    assert [p.page for p in result] == list(range(1, 9))
    for p in result:
        assert "Sammanträdesdatum" not in p.text
        assert "Göteborgs Stad protokoll" not in p.text
        assert "Protokoll nr" not in p.text
        assert p.text.count("nämnden beslutade") == 10


def test_lines_that_differ_only_in_the_page_number_count_as_the_same_header():
    result = strip_repeated_lines(minutes(6))
    assert all("göteborgs stad" not in p.text.lower() for p in result)


def test_section_and_case_numbers_are_never_mistaken_for_a_header():
    """Regression from real Göteborg minutes: "§ 289 Ärendenummer SLK-2025-00035" is content people search for."""

    def page(n: int) -> PageText:
        topic = TOPICS[(n - 1) % len(TOPICS)]
        head = f"Protokoll nr 8\nGöteborgs Stad protokoll {n} (9)\n§ {200 + n} Ärendenummer SLK-2025-{n:05d}\n"
        return PageText(n, head + "\n".join(f"Innehåll om {topic} del {chr(97 + i)}" for i in range(12)))

    result = strip_repeated_lines([page(n) for n in range(1, 10)])

    for p in result:
        assert f"§ {200 + p.page} Ärendenummer SLK-2025-{p.page:05d}" in p.text
        assert "Göteborgs Stad protokoll" not in p.text


def test_a_repeated_footer_is_removed_too():
    def body(n: int) -> str:
        topic = TOPICS[(n - 1) % len(TOPICS)]
        return "\n".join(f"Innehåll om {topic} del {chr(97 + i)}" for i in range(12))

    pages = [PageText(n, body(n) + f"\nSida {n} av 9\nStadsledningskontoret") for n in range(1, 10)]

    result = strip_repeated_lines(pages)

    assert all("Stadsledningskontoret" not in p.text and "Sida" not in p.text for p in result)
    assert all(p.text.count("Innehåll") == 12 for p in result)


def test_a_line_that_repeats_in_the_middle_of_pages_is_kept():
    pages = [
        PageText(n, "\n".join([f"Unik rad {n}-{i}" for i in range(8)] + ["Beslut", f"Unik slutrad {n}"] + [f"Mer {n}-{i}" for i in range(6)]))
        for n in range(1, 9)
    ]

    result = strip_repeated_lines(pages)

    assert all("Beslut" in p.text for p in result)


def test_content_that_appears_on_few_pages_is_kept():
    pages = minutes(8)
    pages[2] = PageText(3, pages[2].text + "\nSammanträdesdatum nämns här i ett beslut.")

    result = strip_repeated_lines(pages)

    assert "nämns här i ett beslut" in result[2].text


def test_short_documents_are_left_alone():
    pages = minutes(3)
    assert strip_repeated_lines(pages) == pages


def test_documents_without_repeats_are_unchanged():
    pages = [PageText(n, f"Helt unik text på sida {n} om olika saker {'x' * n}") for n in range(1, 8)]
    assert strip_repeated_lines(pages) == pages


def test_blank_lines_between_header_lines_do_not_push_them_out_of_range():
    def page(n: int) -> PageText:
        header = "Protokoll nr 8\n \n \nKommunstyrelsen\n \n  \n \nGöteborgs Stad protokoll " + f"{n} (9)\n"
        topic = TOPICS[(n - 1) % len(TOPICS)]
        return PageText(n, header + "\n".join(f"Innehåll om {topic} del {chr(97 + i)}" for i in range(12)))

    result = strip_repeated_lines([page(n) for n in range(1, 10)])

    assert all("Göteborgs Stad protokoll" not in p.text for p in result)


def test_a_document_that_is_all_repeats_is_not_emptied():
    pages = [PageText(n, "Samma rad\nSamma rad igen") for n in range(1, 8)]
    assert strip_repeated_lines(pages) == pages
