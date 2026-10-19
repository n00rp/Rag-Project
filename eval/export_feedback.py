"""Exports rated answers (thumbs up/down in the app) for review, as the raw material for new eval questions.

    ai-service/.venv/Scripts/python eval/export_feedback.py            # writes eval/review/feedback.md
    ai-service/.venv/Scripts/python eval/export_feedback.py --json     # also eval/review/feedback.jsonl

A thumbs-down with a comment is the most useful: it is a real question where the system failed, with a
person's note about why. Review them, decide the expected section and answer, and add the good ones to the eval
set (the "Egna frågor" part of review/evalset-review.md). Reads the app database (DATABASE_URL, like the service).
"""

import argparse
import json
import sys
from pathlib import Path

import psycopg

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "ai-service"))

from app.config import get_settings  # noqa: E402

QUERY = """
SELECT "Id", "Question", "Answer", "Grounded", "Interrupted", "Rating", "FeedbackComment", "SourcesJson", "CreatedAt"
FROM "ChatMessages" WHERE "Rating" IS NOT NULL ORDER BY "Rating" DESC, "CreatedAt"
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="also write review/feedback.jsonl")
    args = ap.parse_args()

    with psycopg.connect(get_settings().database_url) as conn:
        rows = conn.execute(QUERY).fetchall()

    items = []
    for id_, question, answer, grounded, interrupted, rating, comment, sources, created in rows:
        items.append({
            "id": str(id_), "question": question, "answer": answer, "grounded": grounded, "interrupted": interrupted,
            "rating": rating, "comment": comment, "created": created.isoformat(),
            "sources": [{"file": s["fileName"], "page": s["page"]} for s in json.loads(sources)],
        })

    out = ["# Bedömda svar", "", f"{len(items)} svar har fått tumme upp eller ned.", ""]
    for rating, title in (("down", "Tumme ned (där systemet misslyckades)"), ("up", "Tumme upp")):
        group = [i for i in items if i["rating"] == rating]
        out += [f"## {title} ({len(group)})", ""]
        for i in group:
            sources = ", ".join(f"{s['file'][:-4]} s.{s['page']}" for s in i["sources"]) or "inga källor"
            out += [f"### {i['question']}", "", f"**Svar:** {i['answer']}", "", f"**Källor:** {sources}", ""]
            if i["comment"]:
                out += [f"**Kommentar:** {i['comment']}", ""]
    path = HERE / "review" / "feedback.md"
    path.parent.mkdir(exist_ok=True)
    path.write_text("\n".join(out), encoding="utf-8")
    print(f"{len(items)} bedömda svar -> {path.relative_to(HERE.parent)}")
    if args.json:
        (HERE / "review" / "feedback.jsonl").write_text(
            "".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")


if __name__ == "__main__":
    main()
