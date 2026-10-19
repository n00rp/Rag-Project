"""Runs the whole eval with the service's current settings: retrieval metrics, then answer quality.

    ai-service/.venv/Scripts/python eval/run_all.py                      # retrieval + answers with gemma3:12b
    ai-service/.venv/Scripts/python eval/run_all.py --skip-answers       # retrieval only (about a minute)
    ai-service/.venv/Scripts/python eval/run_all.py --models gemma3:12b qwen3:14b --review-sample 10

Needs the database (and Ollama for the answers). Results are written to eval/results/latest-*.json.
The settings come from the environment exactly as the service reads them (EMBEDDING_BACKEND, MIN_SCORE, ...), so
run it with the same values the service runs with.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "ai-service"))
sys.path.insert(0, str(HERE))

from retrieval import (  # noqa: E402
    full_report,
    load_corpus,
    load_questions,
    print_report,
    run_retrieval,
    section_spans,
)

from app.config import get_settings  # noqa: E402
from app.text import normalize_text  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["gemma3:12b"])
    ap.add_argument("--judges", nargs="+", default=["qwen3:14b", "llama3.1:8b"])
    ap.add_argument("--skip-answers", action="store_true")
    ap.add_argument("--review-sample", type=int, default=0)
    ap.add_argument("--label", default="latest")
    args = ap.parse_args()

    settings = get_settings()
    corpus = load_corpus(ROOT / "data" / "goteborg")
    spans = section_spans(corpus)
    full_text = normalize_text(" ".join(p.text for pages in corpus.values() for p in pages)).lower()
    questions = load_questions(HERE / "evalset.jsonl", spans, full_text)

    config = {"strip": settings.strip_page_boilerplate, "header": settings.doc_header, "size": settings.chunk_size,
              "overlap": settings.chunk_overlap, "min_score": settings.min_score, "embedding": settings.embedding_model}
    records = run_retrieval(settings, corpus, spans, questions, strip=settings.strip_page_boilerplate,
                            header=settings.doc_header)
    report = full_report(records)
    print_report(f"{args.label}: retrieval", config, report)
    out = HERE / "results" / f"{args.label}-retrieval.json"
    out.write_text(json.dumps({"config": config, "report": report, "records": records}, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    if args.skip_answers:
        return
    cmd = [sys.executable, str(HERE / "answers.py"), "--models", *args.models, "--judges", *args.judges,
           "--out", str(HERE / "results" / f"{args.label}-answers.json")]
    if args.review_sample:
        cmd += ["--review-sample", str(args.review_sample)]
    print("\n" + " ".join(cmd[1:3]) + " ...")
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
