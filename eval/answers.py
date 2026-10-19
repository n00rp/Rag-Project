"""Answer-quality evaluation: runs the whole RAG chain per LLM and scores the answers.

Run from ai-service/ with its venv (needs the db and Ollama):

    .venv/Scripts/python ../eval/answers.py --models gemma3:12b
    .venv/Scripts/python ../eval/answers.py --models gemma3:12b qwen3:14b --judges qwen3:14b llama3.1:8b gemma3:12b

Per question (only questions with scored=true are part of the numbers; the rest are saved for reading):
  * unanswerable  -> correct iff the model refuses ("Jag hittar inget stöd ...").
  * answerable    -> correct iff it does not refuse AND every judge accepts it against the reference answer
                     (questions without a reference answer: correct iff it cites a source on the right page).
  * cited_ok      -> a source the answer cites ([n]) lies on an expected page.
  * faithful      -> every judge: all claims are supported by the retrieved excerpts.

Judges are LLMs and a model must never judge itself, so for each model under test the judges are the other
models in --judges. All judge verdicts are kept; "correct" needs all of them to agree (strict), and the
agreement rate is reported so that a shaky judge is visible. A sample of answers can be written out for a
human check (--review-sample), and calibrate.py compares the judges with that human verdict.
Latency and VRAM are measured during the generation pass; the judging runs afterwards.
"""

import argparse
import json
import random
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ai-service"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from metrics import bootstrap, fmt, fraction  # noqa: E402
from retrieval import index, load_corpus, load_questions, section_spans, with_overrides  # noqa: E402

from app import db  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.embeddings import build_embedder  # noqa: E402
from app.llm import OllamaLlm  # noqa: E402
from app.rag import answer_question  # noqa: E402
from app.text import normalize_text  # noqa: E402

CITE = re.compile(r"\[(\d+)\]")
JUDGE_SYSTEM = "Du är en sträng men rättvis bedömare av svar på svenska. Svara endast med JSON."


def ollama_chat(base: str, model: str, system: str, user: str, as_json: bool = False) -> str:
    body = {"model": model, "stream": False, "think": False, "options": {"temperature": 0},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if as_json:
        body["format"] = "json"
    r = httpx.post(f"{base}/api/chat", json=body, timeout=300)
    r.raise_for_status()
    return r.json()["message"]["content"]


def vram_mib() -> int:
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout
    return int(out.strip().splitlines()[0])


def unload_all(base: str) -> None:
    for m in httpx.get(f"{base}/api/ps").json().get("models", []):
        httpx.post(f"{base}/api/generate", json={"model": m["name"], "keep_alive": 0}, timeout=60)
    time.sleep(2)


def judge_correct(base, judge, question, reference, answer) -> bool:
    prompt = (f"Fråga: {question}\nFacit: {reference}\nSvar att bedöma: {answer}\n\n"
              "Innehåller svaret samma sakinnehåll som facit (formuleringen får skilja)? "
              "Om facit säger att något INTE gäller eller att frågans antagande är fel, måste svaret säga detsamma. "
              'Svara {"korrekt": true} eller {"korrekt": false}.')
    return bool(json.loads(ollama_chat(base, judge, JUDGE_SYSTEM, prompt, True)).get("korrekt"))


def judge_faithful(base, judge, answer, excerpts) -> bool:
    ctx = "\n\n".join(f"[{i}] {t}" for i, t in enumerate(excerpts, 1))
    prompt = (f"Utdrag:\n{ctx}\n\nSvar: {answer}\n\n"
              "Stöds alla påståenden i svaret av utdragen (inget är påhittat)? "
              'Svara {"stods": true} eller {"stods": false}.')
    return bool(json.loads(ollama_chat(base, judge, JUDGE_SYSTEM, prompt, True)).get("stods"))


def generate(pool, embedder, settings, base, owner, name_of, model, questions) -> list[dict]:
    llm = OllamaLlm(base, model, settings.llm_timeout_seconds)
    runs = []
    for q in questions:
        t = time.perf_counter()
        ans = answer_question(pool=pool, embedder=embedder, llm=llm, settings=settings,
                              owner_id=owner, question=normalize_text(q["question"]))
        dt = time.perf_counter() - t
        runs.append({"q": q, "answer": ans.answer, "grounded": ans.grounded, "support": ans.support, "seconds": dt,
                     "sources": [(name_of[h.document_id], h.page, h.content) for h in ans.sources]})
        print(f"  {model} {q['id']} {dt:5.1f}s {'nej-svar' if not ans.grounded else 'svar'}", flush=True)
    return runs


def judge_batch(base, judge, runs) -> None:
    """Adds this judge's verdicts to every answer that is not a refusal."""
    for r in runs:
        q = r["q"]
        r.setdefault("verdicts", {})
        r.setdefault("faith_verdicts", {})
        if not q["answerable"] or not r["grounded"]:
            continue
        if q.get("answer"):
            r["verdicts"][judge] = judge_correct(base, judge, q["question"], q["answer"], r["answer"])
        r["faith_verdicts"][judge] = judge_faithful(base, judge, r["answer"], [s[2] for s in r["sources"]])


def finish(r, spans) -> None:
    """Combines the verdicts of all judges into the strict flags the summary uses."""
    q = r["q"]
    refused = not r["grounded"]
    r.setdefault("verdicts", {})
    r.setdefault("faith_verdicts", {})
    r["cited_ok"] = None
    r["faithful"] = None
    if not q["answerable"]:
        r["correct"] = r["correct_any"] = refused
        return
    good = {(f, p) for f, n in q["expected"] for p in spans[(f, n)]}
    cited = {int(m) for m in CITE.findall(r["answer"])}
    r["cited_ok"] = any(1 <= i <= len(r["sources"]) and r["sources"][i - 1][:2] in good for i in cited)
    if refused:
        r["correct"] = r["correct_any"] = False
        return
    # no reference answer: the right source is the best evidence we have
    r["correct"] = all(r["verdicts"].values()) if q.get("answer") else r["cited_ok"]
    # the lenient bound: at least one judge accepts it (the true value lies between the strict and this one)
    r["correct_any"] = any(r["verdicts"].values()) if q.get("answer") else r["cited_ok"]
    r["faithful"] = all(r["faith_verdicts"].values())


def summarize(runs: list[dict]) -> dict:
    answerable = [r for r in runs if r["q"]["answerable"]]
    unanswerable = [r for r in runs if not r["q"]["answerable"]]
    given = [r for r in answerable if r["grounded"]]
    judged = [r for r in answerable if r["verdicts"]]
    agree = [len(set(r["verdicts"].values())) == 1 for r in judged if len(r["verdicts"]) > 1]
    lat = sorted(r["seconds"] for r in runs)
    return {
        "n_answerable": len(answerable), "n_unanswerable": len(unanswerable),
        "correct": bootstrap([bool(r["correct"]) for r in answerable], fraction),
        "correct_any": bootstrap([bool(r.get("correct_any")) for r in answerable], fraction),
        "wrongly_refused": bootstrap([not r["grounded"] for r in answerable], fraction),
        "cited_ok": bootstrap([bool(r["cited_ok"]) for r in answerable], fraction),
        "faithful": bootstrap([bool(r["faithful"]) for r in given], fraction),
        "refused_unanswerable": bootstrap([bool(r["correct"]) for r in unanswerable], fraction),
        "judge_agreement": (sum(agree) / len(agree)) if agree else None,
        "partial": sum(r.get("support") == "delvis" for r in answerable),
        "partial_unanswerable": sum(r.get("support") == "delvis" for r in unanswerable),
        "latency_median_s": lat[len(lat) // 2], "latency_p90_s": lat[int(len(lat) * 0.9)],
    }


def by_type(runs: list[dict]) -> dict:
    groups: dict[str, list[bool]] = {}
    for r in runs:
        if r["q"]["answerable"]:
            groups.setdefault(r["q"]["type"], []).append(bool(r["correct"]))
    return {t: {"n": len(v), "correct": sum(v) / len(v)} for t, v in sorted(groups.items())}


def write_review(path: Path, results: dict, n: int, seed: int = 7) -> None:
    """A markdown file with a random sample of answers for a human to mark right/wrong; see calibrate.py."""
    rng = random.Random(seed)
    lines = ["# Bedöm svaren", "",
             "Sätt ett `x` i rätt ruta per svar: **rätt** = svaret är korrekt enligt dokumenten, **fel** = det är fel,",
             "ofullständigt eller påhittat. Facit är bara en hjälp (det kan vara fel eller för snävt).",
             "Fylls i av en människa; `eval/calibrate.py` jämför sedan med domarna.", ""]
    for model, res in results.items():
        pool = [r for r in res["runs"] if r["q"]["scored"] and r["q"]["answerable"] and r["grounded"]]
        for r in rng.sample(pool, min(n, len(pool))):
            q = r["q"]
            lines += [f"## {model} · {q['id']} · {q['type']}", "", f"**Fråga:** {q['question']}", "",
                      f"**Facit:** {q.get('answer') or '(saknas, bedöm mot källan)'}", "",
                      f"**Svar:** {r['answer']}", "",
                      f"**Källor:** {', '.join(f'{s[0][:-4]} s.{s[1]}' for s in r['sources'])}", "",
                      f"- [ ] rätt  - [ ] fel   (domarna: {r['verdicts'] or 'ingen facit'}; id={model}|{q['id']})", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def print_summary(model: str, split: str, group: str, s: dict) -> None:
    agree = f", domarna överens {s['judge_agreement']:.0%}" if s["judge_agreement"] is not None else ""
    print(f"{model} {split:4} {group:19} n={s['n_answerable']}+{s['n_unanswerable']}  korrekt {fmt(s['correct'])} "
          f"(minst en domare: {s['correct_any'][0]:.2f})  "
          f"felaktigt nekade {fmt(s['wrongly_refused'])}  citat rätt {fmt(s['cited_ok'])}  "
          f"nekar obesvarbara {fmt(s['refused_unanswerable'])}  förankrat {fmt(s['faithful'])}{agree}  "
          f"delvis stöd: {s['partial']} av besvarbara, {s['partial_unanswerable']} av obesvarbara  "
          f"latens {s['latency_median_s']:.1f}/{s['latency_p90_s']:.1f}s")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--judges", nargs="+", default=["qwen3:14b", "llama3.1:8b"],
                    help="models that judge; a model is never judged by itself")
    ap.add_argument("--limit", type=int, help="only the first N scored questions (smoke test)")
    ap.add_argument("--split", choices=["dev", "test", "all"], default="all", help="only questions of this part")
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                    help="override a service setting for this run, e.g. --set context_neighbors=1")
    ap.add_argument("--review-sample", type=int, default=0, help="write N answers per model for a human check")
    ap.add_argument("--pdf-dir", type=Path, default=ROOT / "data" / "goteborg")
    ap.add_argument("--evalset", type=Path, default=ROOT / "eval" / "evalset.jsonl")
    ap.add_argument("--out", type=Path, default=ROOT / "eval" / "results" / "answers.json")
    args = ap.parse_args()

    settings = with_overrides(get_settings(), dict(item.split("=", 1) for item in args.set))
    base = settings.ollama_base_url.rstrip("/")
    corpus = load_corpus(args.pdf_dir)
    spans = section_spans(corpus)
    full_text = normalize_text(" ".join(p.text for pages in corpus.values() for p in pages)).lower()
    questions = load_questions(args.evalset, spans, full_text)
    if args.split != "all":
        questions = [q for q in questions if q["split"] == args.split]
    if args.limit:
        keep_a = [q for q in questions if q["answerable"] and q["scored"]][: args.limit]
        keep_n = [q for q in questions if not q["answerable"]][: max(2, args.limit // 4)]
        questions = keep_a + keep_n
    # unscored question types are answered too (to read), but kept out of the numbers
    for m in args.models:
        if not [j for j in args.judges if j != m]:
            raise SystemExit(f"{m} behöver minst en annan domare i --judges")

    embedder = build_embedder(settings)
    db.init_schema(settings.database_url, embedder.dim)
    pool = db.create_pool(settings.database_url)
    owner = f"eval-{uuid.uuid4()}"
    results: dict = {}
    try:
        ids = index(pool, embedder, corpus, owner, settings.strip_page_boilerplate,
                    settings.chunk_size, settings.chunk_overlap, settings.doc_header)
        name_of = {v: k for k, v in ids.items()}
        for model in args.models:
            unload_all(base)
            runs = generate(pool, embedder, settings, base, owner, name_of, model, questions)
            results[model] = {"vram_mib": vram_mib(), "runs": runs}
            print(f"== {model}: VRAM {results[model]['vram_mib']} MiB", flush=True)
        for judge in args.judges:  # one judge at a time, so each judge model is loaded only once
            unload_all(base)
            print(f"-- domare {judge}", flush=True)
            for model, res in results.items():
                if judge != model:  # a model never judges itself
                    judge_batch(base, judge, res["runs"])
        for res in results.values():
            for r in res["runs"]:
                finish(r, spans)
    finally:
        with pool.connection() as conn:
            conn.execute("DELETE FROM rag.chunks WHERE owner_id = %s", (owner,))
        pool.close()

    summary: dict = {}
    for model, res in results.items():
        scored = [r for r in res["runs"] if r["q"]["scored"]]
        summary[model] = {"vram_mib": res["vram_mib"], "by_type": by_type(scored)}
        for split in ("dev", "test"):
            part = [r for r in scored if r["q"]["split"] == split]
            groups = {"alla": part, "utan identifierare": [r for r in part if r["q"]["type"] != "identifierare"]}
            for group, rows in groups.items():
                if rows:
                    summary[model].setdefault(split, {})[group] = summarize(rows)
                    print_summary(model, split, group, summary[model][split][group])
    args.out.write_text(json.dumps({"judges": args.judges, "summary": summary, "results": results},
                                   ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    if args.review_sample:
        write_review(ROOT / "eval" / "review" / "answer-samples.md", results, args.review_sample)
        print(f"Granskningsfil: eval/review/answer-samples.md ({args.review_sample} svar per modell)")


if __name__ == "__main__":
    main()
