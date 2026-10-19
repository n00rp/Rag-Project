"""How far can the LLM judges be trusted? Compares them with a human check.

1. Run answers.py with --review-sample N; it writes eval/review/answer-samples.md.
2. A person marks every answer "rätt" or "fel" (an `x` in the box).
3. Run this script:

    ai-service/.venv/Scripts/python eval/calibrate.py

It reports, per judge and for the strict combination used in the numbers, how often the judge agrees with the
person, how often it accepts an answer the person called wrong (false accept: inflates the scores) and how
often it rejects one the person called right (false reject), plus Cohen's kappa.
"""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINE = re.compile(r"- \[(?P<right>[ xX])\] rätt\s+- \[(?P<wrong>[ xX])\] fel.*?id=(?P<model>[^|]+)\|(?P<qid>\w+)\)")


def read_human(path: Path) -> dict[tuple[str, str], bool]:
    verdicts = {}
    for m in LINE.finditer(path.read_text(encoding="utf-8")):
        right, wrong = m["right"].strip() != "", m["wrong"].strip() != ""
        if right != wrong:  # exactly one box ticked
            verdicts[(m["model"], m["qid"])] = right
    return verdicts


def kappa(pairs: list[tuple[bool, bool]]) -> float:
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    pa, pb = sum(a for a, _ in pairs) / n, sum(b for _, b in pairs) / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    return (observed - expected) / (1 - expected) if expected < 1 else 1.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--review", type=Path, default=ROOT / "eval" / "review" / "answer-samples.md")
    ap.add_argument("--answers", type=Path, default=ROOT / "eval" / "results" / "answers.json")
    args = ap.parse_args()

    human = read_human(args.review)
    if not human:
        raise SystemExit("Inga ifyllda bedömningar hittades i granskningsfilen.")
    data = json.loads(args.answers.read_text(encoding="utf-8"))
    by_key = {(model, r["q"]["id"]): r for model, res in data["results"].items() for r in res["runs"]}

    columns: dict[str, list[tuple[bool, bool]]] = {"strikt (alla domare)": []}
    for key, person in human.items():
        run = by_key.get(key)
        if run is None or not run["verdicts"]:
            continue  # no judge verdict (question without a reference answer)
        columns["strikt (alla domare)"].append((bool(run["correct"]), person))
        for judge, verdict in run["verdicts"].items():
            columns.setdefault(judge, []).append((verdict, person))

    print(f"{len(human)} bedömda svar; {len(columns['strikt (alla domare)'])} med domarutslag\n")
    print(f"{'domare':24} {'n':>4} {'överens':>8} {'falskt godkänt':>15} {'falskt underkänt':>17} {'kappa':>6}")
    for name, pairs in columns.items():
        if not pairs:
            continue
        agree = sum(j == p for j, p in pairs) / len(pairs)
        accepted_wrong = [j for j, p in pairs if not p]
        rejected_right = [not j for j, p in pairs if p]
        fa = f"{sum(accepted_wrong)}/{len(accepted_wrong)}" if accepted_wrong else "-"
        fr = f"{sum(rejected_right)}/{len(rejected_right)}" if rejected_right else "-"
        print(f"{name:24} {len(pairs):4} {agree:8.0%} {fa:>15} {fr:>17} {kappa(pairs):6.2f}")


if __name__ == "__main__":
    main()
