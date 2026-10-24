import re
import unicodedata

# A word broken over two lines ("anställ-\nningsvillkoren"); only lowercase on both sides, so "e-post" is safe.
_LINE_HYPHEN = re.compile(r"(?<=[a-zåäö])-[ \t]*\n(?=[a-zåäö])")


def normalize_text(text: str) -> str:
    """Make extracted or user-typed text comparable and safe to store.

    - NFKC composes decomposed accents (a + U+0308 -> ä, common in macOS/Word exports) so Å/Ä/Ö
      are always single code points, and expands typographic ligatures (ﬁ -> fi, ﬂ -> fl) that
      InDesign-style PDFs use and that would otherwise break matching on e.g. "finansiering".
      It also turns non-breaking spaces into regular spaces.
    - Words hyphenated at a line break are joined, otherwise neither search nor the model sees the word.
    - NUL bytes are removed: pypdf can emit them and Postgres text columns reject them.
    """
    return _LINE_HYPHEN.sub("", unicodedata.normalize("NFKC", text).replace("\x00", ""))
