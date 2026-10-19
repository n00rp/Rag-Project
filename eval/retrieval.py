"""Retrieval evaluation: does the right page show up in the top-k chunks?

Run from ai-service/ with its venv (needs the db: docker compose up -d db):

    .venv/Scripts/python ../eval/retrieval.py --label baseline --doc-header
    .venv/Scripts/python ../eval/retrieval.py --label no-hybrid --doc-header --set hybrid_identifiers=false
    .venv/Scripts/python ../eval/retrieval.py --label size500 --doc-header --size 500 --overlap 75

It calls the same function as the service (app.rag.retrieve), so routing, date filter and the refusal threshold
are measured as they behave in production. Settings come from the environment like in the service; --set name=value
overrides one for this run. Each config is indexed under a throwaway owner_id and removed afterwards.

Correct page = any page of an expected section (§) in evalset.jsonl; spans are derived from the PDFs.
The eval set is split into dev (tune on it) and test (look at it when a decision is made). Everything is shown
with 95 % bootstrap intervals. Questions with scored=false (summaries, counts, ...) are not part of the numbers.
"""

import argparse
import json
import re
import sys
import uuid
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ai-service"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from metrics import auc, best_threshold, bootstrap, fmt, fraction, mrr, recall_at  # noqa: E402

from app import db, rag  # noqa: E402
from app.boilerplate import strip_repeated_lines  # noqa: E402
from app.chunking import add_header, chunk_pages, document_header  # noqa: E402
from app.config import Settings, get_settings  # noqa: E402
from app.embeddings import build_embedder  # noqa: E402
from app.pdf import extract_pages  # noqa: E402
from app.text import normalize_text  # noqa: E402

SECTION = re.compile(r"^§ ?(\d+) Ärendenummer", re.M)


def load_corpus(pdf_dir: Path) -> dict[str, list]:
    return {p.name: extract_pages(p.read_bytes()) for p in sorted(pdf_dir.glob("*.pdf"))}


def section_spans(corpus) -> dict[tuple[str, int], range]:
    """(file, §) -> pages from where the § starts to the page before the next § starts."""
    spans = {}
    for name, pages in corpus.items():
        starts = [(int(m.group(1)), p.page) for p in pages for m in SECTION.finditer(p.text)]
        for i, (num, start) in enumerate(starts):
            end = starts[i + 1][1] - 1 if i + 1 < len(starts) else pages[-1].page
            spans[(name, num)] = range(start, max(start, end) + 1)
    return spans


def index(pool, embedder, corpus, owner, strip, size, overlap, header=False) -> dict:
    ids = {}
    for name, pages in corpus.items():
        ids[name] = uuid.uuid5(uuid.NAMESPACE_URL, name)
        used = strip_repeated_lines(pages) if strip else pages
        chunks = chunk_pages(used, size, overlap)
        if header:
            chunks = add_header(chunks, document_header(pages))
        db.replace_document_chunks(pool, owner, ids[name], chunks, embedder.embed_passages([c.text for c in chunks]))
    return ids


def load_questions(path: Path, spans, full_text: str) -> list[dict]:
    """Reads the eval set and guards it: every expected § must exist, every "absent" term must be absent."""
    questions = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for q in questions:
        q.setdefault("scored", True)
        q.setdefault("split", "dev")
        for f, n in q.get("expected", []):
            assert (f, n) in spans, f"{q['id']}: § {n} finns inte i {f}"
        for term in q.get("absent_terms", []):
            assert term.lower() not in full_text, f"{q['id']}: '{term}' finns i dokumenten"
    return questions


def with_overrides(settings: Settings, overrides: dict[str, str]) -> Settings:
    """A copy of the settings with some values replaced (pydantic converts "false" / "0.5" to the right type)."""
    return Settings(**{**settings.model_dump(), **overrides})


def run_retrieval(settings, corpus, spans, questions, *, strip=True, size=None, overlap=None, header=True,
                  top_k=10) -> list[dict]:
    """One record per scored question: rank of the first correct hit (None if not in top-k), whether the service
    would have refused, and the cosine of the best hit."""
    size = size or settings.chunk_size
    overlap = settings.chunk_overlap if overlap is None else overlap
    embedder = build_embedder(settings)
    db.init_schema(settings.database_url, embedder.dim)  # adds the keyword column if the service has not run yet
    pool = db.create_pool(settings.database_url)
    owner = f"eval-{uuid.uuid4()}"
    records = []
    try:
        ids = index(pool, embedder, corpus, owner, strip, size, overlap, header)
        name_of = {v: k for k, v in ids.items()}
        for q in questions:
            if not q["scored"]:
                continue
            found = rag.retrieve(pool=pool, embedder=embedder, settings=settings, owner_id=owner,
                                 question=q["question"], top_k=top_k)
            hits = found.hits
            record = {"id": q["id"], "type": q["type"], "split": q["split"], "answerable": q["answerable"],
                      "question": q["question"], "top1": hits[0].score if hits else 0.0, "refused": found.refused,
                      "rank": None, "top3": [(name_of[h.document_id], h.page) for h in hits[:3]]}
            if q["answerable"]:
                good = [(f, spans[(f, n)]) for f, n in q["expected"]]
                record["rank"] = next(
                    (i for i, h in enumerate(hits, 1)
                     if any(name_of[h.document_id] == f and h.page in pages for f, pages in good)), None)
            records.append(record)
    finally:
        with pool.connection() as conn:
            conn.execute("DELETE FROM rag.chunks WHERE owner_id = %s", (owner,))
        pool.close()
    return records


def summarize(records: list[dict], threshold: float | None = None) -> dict:
    """Metrics with 95 % intervals for one group. "answered"/"refused" are what the service did with its own
    threshold; `threshold` (chosen on dev) is only used for the AUC-style comparison of top-1 scores."""
    answerable = [r for r in records if r["answerable"]]
    unanswerable = [r for r in records if not r["answerable"]]
    ranks = [r["rank"] for r in answerable]
    out = {
        "n_answerable": len(answerable), "n_unanswerable": len(unanswerable),
        "recall@1": bootstrap(ranks, recall_at(1)), "recall@3": bootstrap(ranks, recall_at(3)),
        "recall@5": bootstrap(ranks, recall_at(5)), "mrr": bootstrap(ranks, mrr),
    }
    if answerable and unanswerable:
        out["auc"] = auc([r["top1"] for r in answerable], [r["top1"] for r in unanswerable])
        out["answered"] = bootstrap([not r["refused"] for r in answerable], fraction)
        out["refused"] = bootstrap([r["refused"] for r in unanswerable], fraction)
        if threshold is not None:
            out["threshold"] = threshold
    return out


GROUPS = {
    "alla": lambda r: True,
    "utan identifierare": lambda r: r["type"] != "identifierare",
    "bara identifierare": lambda r: r["type"] == "identifierare",
}


def full_report(records: list[dict]) -> dict:
    """dev and test, each for all questions / without identifier questions / identifier questions only.
    The best top-1 threshold on dev is reported for reference (the service uses settings.min_score)."""
    dev = [r for r in records if r["split"] == "dev"]
    pos, neg = [r["top1"] for r in dev if r["answerable"]], [r["top1"] for r in dev if not r["answerable"]]
    threshold = best_threshold(pos, neg) if pos and neg else None
    by_type = defaultdict(list)
    for r in records:
        if r["answerable"]:
            by_type[r["type"]].append(r["rank"])
    report = {"threshold_from_dev": threshold}
    for part in ("dev", "test"):
        rows = [r for r in records if r["split"] == part]
        report[part] = {name: summarize([r for r in rows if keep(r) and (r["answerable"] or name == "alla")], threshold)
                        for name, keep in GROUPS.items()}
    report["by_type"] = {t: {"n": len(v), "mrr": mrr(v), "recall@3": recall_at(3)(v)} for t, v in sorted(by_type.items())}
    return report


def print_report(label: str, config: dict, rep: dict) -> None:
    print(f"\n== {label}  {config}")
    for part in ("dev", "test"):
        for name in GROUPS:
            s = rep[part][name]
            if not s["n_answerable"]:
                continue
            print(f"{part:4} {name:19} n={s['n_answerable']:3}  R@1 {fmt(s['recall@1'])}  R@3 {fmt(s['recall@3'])}  "
                  f"R@5 {fmt(s['recall@5'])}  MRR {fmt(s['mrr'], 3)}")
        s = rep[part]["alla"]
        if "answered" in s:
            print(f"     nej-svar (tjänstens tröskel, n={s['n_unanswerable']}): "
                  f"svarar på {fmt(s['answered'])} av besvarbara, nekar {fmt(s['refused'])} av obesvarbara, AUC {s['auc']:.2f}")
    print("per typ: " + "  ".join(f"{t} {v['n']}st MRR {v['mrr']:.2f}" for t, v in rep["by_type"].items()))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="run")
    ap.add_argument("--no-strip", action="store_true")
    ap.add_argument("--doc-header", action="store_true", help="prefix every chunk with the document context")
    ap.add_argument("--size", type=int)
    ap.add_argument("--overlap", type=int)
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                    help="override a service setting for this run, e.g. --set hybrid_identifiers=false")
    ap.add_argument("--pdf-dir", type=Path, default=ROOT / "data" / "goteborg")
    ap.add_argument("--evalset", type=Path, default=ROOT / "eval" / "evalset.jsonl")
    ap.add_argument("--json", type=Path, help="write the full result here")
    ap.add_argument("-v", "--verbose", action="store_true", help="list the dev misses (rank > 5)")
    args = ap.parse_args()

    overrides = dict(item.split("=", 1) for item in args.set)
    settings = with_overrides(get_settings(), overrides)
    corpus = load_corpus(args.pdf_dir)
    spans = section_spans(corpus)
    full_text = normalize_text(" ".join(p.text for pages in corpus.values() for p in pages)).lower()
    questions = load_questions(args.evalset, spans, full_text)

    records = run_retrieval(settings, corpus, spans, questions, strip=not args.no_strip, size=args.size,
                            overlap=args.overlap, header=args.doc_header, top_k=args.top_k)
    rep = full_report(records)
    config = {"strip": not args.no_strip, "header": args.doc_header, "size": args.size or settings.chunk_size,
              "overlap": settings.chunk_overlap if args.overlap is None else args.overlap, **overrides}
    print_report(args.label, config, rep)
    if args.verbose:
        for r in records:
            if r["answerable"] and r["split"] == "dev" and (r["rank"] is None or r["rank"] > 5):
                print(f" miss {r['id']} rank={r['rank']}: {r['question']}\n      top3: {r['top3']}")
    if args.json:
        args.json.write_text(json.dumps({"label": args.label, "config": config, "report": rep, "records": records},
                                        ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
