"""Compares saved retrieval runs (results/*.json from retrieval.py) side by side, and can simulate a router that
picks one run for questions that match a pattern and another run for the rest.

    ai-service/.venv/Scripts/python eval/compare_runs.py results/e3/vec.json results/e3/h-df1.json
    ai-service/.venv/Scripts/python eval/compare_runs.py --router results/e3/vec.json results/e3/h-df1.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from metrics import bootstrap, fmt, mrr, recall_at  # noqa: E402

IDENTIFIER = re.compile(r"SLK-\d{4}-\d+|§\s?\d+")


def load(path: str) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["records"]


def rows(records: list[dict], split: str, group: str) -> list[int | None]:
    keep = {
        "alla": lambda r: True,
        "utan id": lambda r: r["type"] != "identifierare",
        "bara id": lambda r: r["type"] == "identifierare",
        "mönster": lambda r: bool(IDENTIFIER.search(r["question"])),
        "inget mönster": lambda r: not IDENTIFIER.search(r["question"]),
    }[group]
    return [r["rank"] for r in records if r["answerable"] and r["split"] == split and keep(r)]


def router(default: list[dict], special: list[dict]) -> list[dict]:
    by_id = {r["id"]: r for r in special}
    return [by_id[r["id"]] if IDENTIFIER.search(r["question"]) else r for r in default]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--router", action="store_true", help="first run for most questions, the others where the question has a case or § number")
    args = ap.parse_args()

    named = {Path(p).stem: load(p) for p in args.runs}
    if args.router:
        first, *others = list(named.items())
        for name, recs in others:
            named[f"router({first[0]}+{name})"] = router(first[1], recs)

    groups = ["alla", "utan id", "bara id"]
    print(f"{'körning':34} " + " | ".join(f"{s} {g:8} MRR     R@1 " for s in ("dev", "test") for g in groups))
    for name, recs in named.items():
        cells = []
        for split in ("dev", "test"):
            for group in groups:
                ranks = rows(recs, split, group)
                cells.append(f"{mrr(ranks):.3f} {recall_at(1)(ranks):.2f}" if ranks else "   -   ")
        print(f"{name:34} " + " | ".join(f"{c:^26}" for c in cells))
    if args.router:
        print("\nmed intervall (dev, alla):")
        for name, recs in named.items():
            print(f"  {name:34} MRR {fmt(bootstrap(rows(recs, 'dev', 'alla'), mrr), 3)}   R@1 {fmt(bootstrap(rows(recs, 'dev', 'alla'), recall_at(1)))}")


if __name__ == "__main__":
    main()
