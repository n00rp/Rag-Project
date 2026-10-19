"""Reads the filled-in eval/review/evalset-review.md and stores the decisions in eval/review/decisions.json.

    ai-service/.venv/Scripts/python eval/apply_review.py
    ai-service/.venv/Scripts/python eval/build_evalset.py      # applies the decisions to evalset.jsonl

build_evalset.py marks "stämmer" questions as reviewed, drops "ta bort", takes "ändra" text and appends your own
questions. Running both again later is safe: the decisions file is the single place where review lives.
"""

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
BLOCK = re.compile(r"^## (?P<id>[qn]\d+) ·.*?(?=^## |^# |\Z)", re.M | re.S)
TICK = re.compile(r"- \[(?P<a>[ xX])\] stämmer\s+- \[(?P<b>[ xX])\] ändra\s+- \[(?P<c>[ xX])\] ta bort")


def main() -> None:
    review = HERE / "review" / "evalset-review.md"
    text = review.read_text(encoding="utf-8")
    decisions: dict[str, dict] = {}
    skipped = 0
    for block in BLOCK.finditer(text):
        tick = TICK.search(block.group(0))
        if not tick:
            continue
        marked = [name for name, key in (("stämmer", "a"), ("ändra", "b"), ("ta bort", "c")) if tick[key].strip()]
        if len(marked) != 1:
            skipped += 1  # nothing or several boxes ticked: not decided
            continue
        decision = {"verdict": marked[0]}
        if marked[0] == "ändra":
            question = re.search(r"^Ny fråga:[ \t]*(.*)$", block.group(0), re.M)
            answer = re.search(r"^Nytt facit:[ \t]*(.*)$", block.group(0), re.M)
            if question and question.group(1).strip():
                decision["question"] = question.group(1).strip()
            if answer and answer.group(1).strip():
                decision["answer"] = answer.group(1).strip()
        decisions[block["id"]] = decision

    own = []
    tail = text.split("<!-- EGNA FRÅGOR NEDAN -->", 1)
    if len(tail) == 2:
        for line in tail[1].splitlines():
            line = line.strip().strip("`")
            if "|" in line:
                parts = [p.strip() for p in line.split("|")]
                if parts[0]:
                    own.append({"question": parts[0], "answer": parts[1] if len(parts) > 1 else "",
                                "where": parts[2] if len(parts) > 2 else ""})
    (HERE / "review").mkdir(exist_ok=True)
    out = HERE / "review" / "decisions.json"
    out.write_text(json.dumps({"decisions": decisions, "own": own}, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {v: sum(d["verdict"] == v for d in decisions.values()) for v in ("stämmer", "ändra", "ta bort")}
    print(f"{len(decisions)} beslut ({counts}), {skipped} ej avgjorda, {len(own)} egna frågor -> {out.name}")


if __name__ == "__main__":
    main()
