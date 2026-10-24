"""Reading order for pages with a two-column block (e.g. the AB agreements: "kommun/region" next to "övriga").

pypdf reads such a block row by row, so the two columns are interleaved ("a) För en arbetstagare ... b) För en ...")
and the model answers from the wrong column. Here the words are grouped into lines, a vertical gutter is looked for,
and every run of lines that stays on one side of it is read column by column. Pages without such a block return None
and keep the text pypdf produced, so single-column documents are unaffected.
"""
from collections import Counter

LINE_TOLERANCE = 3.0  # points; words whose tops are this close are on the same line
MIN_GAP = 15.0  # a gap this wide inside a line can be a gutter (normal word spacing is 2-4 points)
MIN_NARROW_GAP = 6.0  # once the gutter is known, a line with at least this gap there is still a column line
MAX_ROW_SHARE = 0.6  # above this share of 'both' lines it is a table read row by row (e.g. abbreviation | meaning)
MIN_COLUMN_WORDS = 25  # prose columns are long; label/value tables and signature blocks are not worth reordering
MIN_BOTH_LINES = 2  # lines with text on both sides of the gutter needed to call a run a two-column block


def _lines(words: list[dict]) -> list[list[dict]]:
    lines: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if lines and abs(lines[-1][0]["top"] - w["top"]) <= LINE_TOLERANCE:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


def _gutter(lines: list[list[dict]], width: float) -> float | None:
    """The gutter, found from where the right column starts (it is the same on every line, unlike where the left one
    ends), or None."""
    starts = Counter()
    for line in lines:
        for left, right in zip(line, line[1:]):
            if right["x0"] - left["x1"] >= MIN_GAP and 0.3 * width <= right["x0"] <= 0.75 * width:
                starts[round(right["x0"] / 10) * 10] += 1
    if not starts:
        return None
    start, count = starts.most_common(1)[0]
    return start - 8.0 if count >= MIN_BOTH_LINES else None


def _side(line: list[dict], gx: float) -> tuple[str, bool]:
    """('both' | 'left' | 'right' | 'cross', strong): 'both' means a gap at the gutter and nothing spanning it, strong that
    the gap is wide. Text in a column can run close to the gutter, so a narrow gap still counts as 'both'."""
    left = [w for w in line if w["x1"] <= gx + 5]
    right = [w for w in line if w["x0"] >= gx - 5]
    if len(left) + len(right) < len(line):
        return "cross", False
    if left and right:
        gap = right[0]["x0"] - left[-1]["x1"]
        return ("both", gap >= MIN_GAP) if gap >= MIN_NARROW_GAP else ("cross", False)
    return ("left" if left else "right"), False


def _text(line: list[dict]) -> str:
    return " ".join(w["text"] for w in line)


def column_text(words: list[dict], width: float) -> str | None:
    """The page text with two-column blocks read column by column, or None when the page has none."""
    lines = _lines(words)
    gx = _gutter(lines, width)
    if gx is None:
        return None
    classified = [_side(line, gx) for line in lines]
    sides = [c[0] for c in classified]
    strong = [c[1] for c in classified]

    out: list[str] = []
    found = False
    i = 0
    while i < len(lines):
        if sides[i] == "cross":
            out.append(_text(lines[i]))
            i += 1
            continue
        j = i
        while j < len(lines) and sides[j] != "cross":
            j += 1
        run = range(i, j)
        both = sum(sides[k] == "both" for k in run)
        words_left = sum(sum(w["x1"] <= gx + 5 for w in lines[k]) for k in run)
        words_right = sum(sum(w["x0"] >= gx - 5 for w in lines[k]) for k in run)
        if (sum(strong[k] for k in run) >= MIN_BOTH_LINES and both <= MAX_ROW_SHARE * len(run)
                and min(words_left, words_right) >= MIN_COLUMN_WORDS):
            found = True
            for side in ("left", "right"):
                for k in run:
                    part = [w for w in lines[k] if (w["x1"] <= gx + 5 if side == "left" else w["x0"] >= gx - 5)]
                    if part:
                        out.append(_text(part))
        else:
            out.extend(_text(lines[k]) for k in run)
        i = j
    return "\n".join(out) if found else None
