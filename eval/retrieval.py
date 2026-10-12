"""Retrieval evaluation: does the right page show up in the top-k chunks?

Run from ai-service/ with its venv (needs the db: docker compose up -d db):

    .venv/Scripts/python ../eval/retrieval.py --label baseline
    .venv/Scripts/python ../eval/retrieval.py --label no-strip --no-strip
    .venv/Scripts/python ../eval/retrieval.py --label size500 --size 500 --overlap 75

Each config is indexed under a throwaway owner_id and removed afterwards, so real data is untouched.
Correct page = any page of the expected section (§) in evalset.jsonl; spans are derived from the PDFs.
Unanswerable questions measure the "no support" threshold: their top-1 score vs the answerable ones.
"""

import argparse
import json
import re
import sys
import uuid
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ai-service"))

from app import db  # noqa: E402
from app.boilerplate import strip_repeated_lines  # noqa: E402
from app.chunking import chunk_pages, document_header  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.embeddings import build_embedder  # noqa: E402
from app.pdf import extract_pages  # noqa: E402
from app.text import normalize_text  # noqa: E402

SECTION = re.compile(r"^§ ?(\d+) Ärendenummer", re.M)
KS = (1, 3, 5, 10)


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
            prefix = document_header(pages)
            chunks = [replace(c, text=f"{prefix}. {c.text}") for c in chunks]
        db.replace_document_chunks(pool, owner, ids[name], chunks, embedder.embed_passages([c.text for c in chunks]))
    return ids


def auc(pos: list[float], neg: list[float]) -> float:
    """P(answerable top-1 score > unanswerable top-1 score); 0.5 = no separation."""
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def best_threshold(pos: list[float], neg: list[float]) -> tuple[float, float, float]:
    """Threshold maximising (answered-correctly + refused-correctly) / 2; returns (t, recall_kept, refused)."""
    best = (0.0, -1.0, 0.0, 0.0)
    for t in sorted(set(pos + neg)):
        kept = sum(s >= t for s in pos) / len(pos)
        refused = sum(s < t for s in neg) / len(neg)
        if (kept + refused) / 2 > best[1]:
            best = (t, (kept + refused) / 2, kept, refused)
    return best[0], best[2], best[3]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="run")
    ap.add_argument("--no-strip", action="store_true")
    ap.add_argument("--doc-header", action="store_true", help="prefix every chunk with the document context")
    ap.add_argument("--size", type=int)
    ap.add_argument("--overlap", type=int)
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--pdf-dir", type=Path, default=ROOT / "data" / "goteborg")
    ap.add_argument("--evalset", type=Path, default=ROOT / "eval" / "evalset.jsonl")
    ap.add_argument("--json", type=Path, help="write the full result here")
    ap.add_argument("-v", "--verbose", action="store_true", help="list every miss")
    args = ap.parse_args()

    settings = get_settings()
    size = args.size or settings.chunk_size
    overlap = args.overlap if args.overlap is not None else settings.chunk_overlap
    strip = not args.no_strip

    corpus = load_corpus(args.pdf_dir)
    spans = section_spans(corpus)
    questions = [json.loads(line) for line in args.evalset.read_text(encoding="utf-8").splitlines() if line.strip()]

    # Guard the evalset itself: every expected § must exist, every "absent" term must really be absent.
    full_text = normalize_text(" ".join(p.text for pages in corpus.values() for p in pages)).lower()
    for q in questions:
        for f, n in q.get("expected", []):
            assert (f, n) in spans, f"{q['id']}: § {n} finns inte i {f}"
        for term in q.get("absent_terms", []):
            assert term.lower() not in full_text, f"{q['id']}: '{term}' finns i dokumenten"

    embedder = build_embedder(settings)
    pool = db.create_pool(settings.database_url)
    owner = f"eval-{uuid.uuid4()}"
    try:
        ids = index(pool, embedder, corpus, owner, strip, size, overlap, args.doc_header)
        name_of = {v: k for k, v in ids.items()}
        ranks, pos, neg, misses = {}, [], [], []
        for q in questions:
            hits = db.search(pool, owner, embedder.embed_query(normalize_text(q["question"])), args.top_k)
            top1 = hits[0].score if hits else 0.0
            if not q["answerable"]:
                neg.append(top1)
                continue
            pos.append(top1)
            good = [spans[(f, n)] for f, n in q["expected"]]
            rank = next(
                (i for i, h in enumerate(hits, 1) if any(name_of[h.document_id] == f and h.page in r
                                                         for (f, _), r in zip(q["expected"], good))),
                None,
            )
            ranks[q["id"]] = rank
            if rank is None or rank > 5:
                misses.append((q["id"], rank, q["question"], [(name_of[h.document_id][:-4], h.page) for h in hits[:3]]))
    finally:
        with pool.connection() as conn:
            conn.execute("DELETE FROM rag.chunks WHERE owner_id = %s", (owner,))
        pool.close()

    n = len(ranks)
    recall = {k: sum(r is not None and r <= k for r in ranks.values()) / n for k in KS}
    mrr = sum(1 / r for r in ranks.values() if r) / n
    t, kept, refused = best_threshold(pos, neg)
    result = {
        "label": args.label, "strip": strip, "doc_header": args.doc_header, "size": size, "overlap": overlap, "n_answerable": n,
        "recall": recall, "mrr": mrr, "auc": auc(pos, neg),
        "threshold": {"value": t, "answerable_kept": kept, "unanswerable_refused": refused},
        "top1_mean": {"answerable": sum(pos) / n, "unanswerable": sum(neg) / len(neg)},
        "ranks": ranks,
    }
    print(f"\n== {args.label}  (strip={strip}, header={args.doc_header}, size={size}, overlap={overlap}, n={n})")
    print("recall@k  " + "  ".join(f"@{k}={recall[k]:.2f}" for k in KS) + f"   MRR={mrr:.3f}")
    print(f"nej-svar  AUC={result['auc']:.2f}  bästa tröskel {t:.3f}: behåller {kept:.0%} av besvarbara, "
          f"nekar {refused:.0%} av obesvarbara  (top-1 snitt {result['top1_mean']['answerable']:.3f} vs "
          f"{result['top1_mean']['unanswerable']:.3f})")
    if args.verbose:
        for qid, rank, text, got in misses:
            print(f" miss {qid} rank={rank}: {text}\n      top3: {got}")
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
