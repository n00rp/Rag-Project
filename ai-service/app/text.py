import unicodedata


def normalize_text(text: str) -> str:
    """Make extracted or user-typed text comparable and safe to store.

    - NFKC composes decomposed accents (a + U+0308 -> ä, common in macOS/Word exports) so Å/Ä/Ö
      are always single code points, and expands typographic ligatures (ﬁ -> fi, ﬂ -> fl) that
      InDesign-style PDFs use and that would otherwise break matching on e.g. "finansiering".
      It also turns non-breaking spaces into regular spaces.
    - NUL bytes are removed: pypdf can emit them and Postgres text columns reject them.
    """
    return unicodedata.normalize("NFKC", text).replace("\x00", "")
