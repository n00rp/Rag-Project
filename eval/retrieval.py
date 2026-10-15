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


HYBRID_SQL = """
WITH vec AS (
    SELECT id, row_number() OVER (ORDER BY embedding <=> %(q)s) AS r FROM rag.chunks
    WHERE owner_id = %(owner)s ORDER BY embedding <=> %(q)s LIMIT %(pool)s
), fts AS (
    SELECT id, row_number() OVER (ORDER BY ts_rank_cd(to_tsvector('swedish', content), query) DESC) AS r
    FROM rag.chunks, to_tsquery(%(cfg)s, %(tsq)s) AS query
    WHERE owner_id = %(owner)s AND to_tsvector('swedish', content) @@ query
    ORDER BY ts_rank_cd(to_tsvector('swedish', content), query) DESC LIMIT %(pool)s
)
SELECT c.document_id, c.page, c.chunk_index, c.content, 1 - (c.embedding <=> %(q)s) AS cosine,
       coalesce(%(wv)s / (%(rrf)s + vec.r), 0) + coalesce(%(wf)s / (%(rrf)s + fts.r), 0) AS score
FROM rag.chunks c LEFT JOIN vec ON vec.id = c.id LEFT JOIN fts ON fts.id = c.id
WHERE vec.id IS NOT NULL OR fts.id IS NOT NULL
ORDER BY score DESC LIMIT %(k)s
"""


def rare_terms(pool, owner) -> tuple[dict[str, int], int]:
    """Document frequency of every stemmed word among the owner's chunks (for the --idf filter)."""
    with pool.connection() as conn:
        n = conn.execute("SELECT count(*) FROM rag.chunks WHERE owner_id = %s", (owner,)).fetchone()[0]
        rows = conn.execute(
            "SELECT word, ndoc FROM ts_stat(%s)",
            (f"SELECT to_tsvector('swedish', content) FROM rag.chunks WHERE owner_id = '{owner}'",),
        ).fetchall()
    return dict(rows), n


def search_hybrid(pool, owner, text, q_emb, k, wv=1.0, wf=1.0, rrf=60, pool_size=30, df=None, max_df=0.05):
    """Vector + Postgres full-text (Swedish stemming, OR of the question's words), fused with Reciprocal Rank Fusion.
    Hit.score is the cosine of the chunk so min_score keeps its meaning; the ranking is by RRF.
    With df: only words found in at most max_df of the chunks are used, so common words do not add noise."""
    if df is None:
        words = list(dict.fromkeys(re.findall(r"\w+", text.lower())))
        cfg = "swedish"
    else:
        with pool.connection() as conn:
            stems = conn.execute("SELECT unnest(tsvector_to_array(to_tsvector('swedish', %s)))", (text,)).fetchall()
        words = [s[0] for s in stems if df[0].get(s[0], 0) <= max_df * df[1]]
        cfg = "simple"  # already stemmed
    tsq = " | ".join(f"'{w}'" for w in words) or "'x'"
    params = dict(q=q_emb, owner=owner, tsq=tsq, k=k, pool=pool_size, wv=wv, wf=wf, rrf=rrf, cfg=cfg)
    with pool.connection() as conn:
        rows = conn.execute(HYBRID_SQL, params).fetchall()
    return [db.Hit(r[0], r[1], r[2], r[3], r[4]) for r in rows]


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
    ap.add_argument("--hybrid", action="store_true", help="vector + Swedish full-text search fused with RRF")
    ap.add_argument("--idf", action="store_true", help="hybrid: only use words found in few chunks")
    ap.add_argument("--max-df", type=float, default=0.05, help="--idf: highest share of chunks a word may occur in")
    ap.add_argument("--wf", type=float, default=1.0, help="weight of the full-text ranking in the fusion")
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
        df = rare_terms(pool, owner) if args.idf else None
        ranks, pos, neg, misses = {}, [], [], []
        for q in questions:
            text = normalize_text(q["question"])
            q_emb = embedder.embed_query(text)
            hits = (search_hybrid(pool, owner, text, q_emb, args.top_k, wf=args.wf, df=df, max_df=args.max_df) if args.hybrid
                    else db.search(pool, owner, q_emb, args.top_k))
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
        "label": args.label, "hybrid": args.hybrid, "idf": args.idf, "max_df": args.max_df, "wf": args.wf, "strip": strip, "doc_header": args.doc_header, "size": size, "overlap": overlap, "n_answerable": n,
        "recall": recall, "mrr": mrr, "auc": auc(pos, neg),
        "threshold": {"value": t, "answerable_kept": kept, "unanswerable_refused": refused},
        "top1_mean": {"answerable": sum(pos) / n, "unanswerable": sum(neg) / len(neg)},
        "ranks": ranks,
    }
    print(f"\n== {args.label}  (hybrid={args.hybrid}, strip={strip}, header={args.doc_header}, size={size}, overlap={overlap}, n={n})")
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
