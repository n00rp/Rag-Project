"""Re-summarises a saved answers run (no model calls), e.g. after the summary format changed.

    ai-service/.venv/Scripts/python eval/summarize_answers.py eval/results/baseline-v2-answers.json
"""

import json
import sys
from pathlib import Path

from answers import by_type, print_summary, summarize


def main() -> None:
    path = Path(sys.argv[1])
    data = json.loads(path.read_text(encoding="utf-8"))
    for model, res in data["results"].items():
        runs = res["runs"]
        for r in runs:
            if "correct_any" not in r:  # runs saved before the lenient bound existed
                q = r["q"]
                r["correct_any"] = (any(r["verdicts"].values()) if q.get("answer") and r["verdicts"] else r["correct"])
        scored = [r for r in runs if r["q"]["scored"]]
        print(f"== {model} (VRAM {res['vram_mib']} MiB, domare: {data['judges']})")
        for split in ("dev", "test"):
            part = [r for r in scored if r["q"]["split"] == split]
            groups = {"alla": part, "utan identifierare": [r for r in part if r["q"]["type"] != "identifierare"]}
            for group, rows in groups.items():
                if rows:
                    print_summary(model, split, group, summarize(rows))
        print("per typ:", {t: f"{v['n']}st {v['correct']:.0%}" for t, v in by_type(scored).items()})


if __name__ == "__main__":
    main()
