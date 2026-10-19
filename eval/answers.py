"""Answer-quality evaluation: runs the whole RAG chain per LLM and scores the answers.

Run from ai-service/ with its venv (needs the db and Ollama):

    .venv/Scripts/python ../eval/answers.py --models qwen3:14b gemma3:12b llama3.1:8b --judge qwen3:14b

Per question:
  * unanswerable  -> correct iff the model refuses ("Jag hittar inget stöd ...").
  * answerable    -> correct iff it does not refuse AND the judge accepts it against the reference answer
                     (questions without a reference answer: judged on the cited source page only).
  * cited_ok      -> a source the answer cites ([n]) lies on the expected page.
  * faithful      -> judge: every claim in the answer is supported by the retrieved excerpts.
Latency and VRAM are measured during the generation pass; the judge runs afterwards.
The judge is itself an LLM (default qwen3:14b, so it is biased towards its own answers): spot-check by hand.
"""

import argparse
import json
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

from retrieval import index, load_corpus, section_spans  # noqa: E402

from app import db  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.embeddings import build_embedder  # noqa: E402
from app.llm import OllamaLlm  # noqa: E402
from app.rag import answer_question  # noqa: E402

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
              'Innehåller svaret samma sakinnehåll som facit (formuleringen får skilja)? '
              'Svara {"korrekt": true} eller {"korrekt": false}.')
    return bool(json.loads(ollama_chat(base, judge, JUDGE_SYSTEM, prompt, True)).get("korrekt"))


def judge_faithful(base, judge, answer, excerpts) -> bool:
    ctx = "\n\n".join(f"[{i}] {t}" for i, t in enumerate(excerpts, 1))
    prompt = (f"Utdrag:\n{ctx}\n\nSvar: {answer}\n\n"
              'Stöds alla påståenden i svaret av utdragen (inget är påhittat)? '
              'Svara {"stods": true} eller {"stods": false}.')
    return bool(json.loads(ollama_chat(base, judge, JUDGE_SYSTEM, prompt, True)).get("stods"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--judge", default="qwen3:14b")
    ap.add_argument("--limit", type=int, help="only the first N questions (smoke test)")
    ap.add_argument("--pdf-dir", type=Path, default=ROOT / "data" / "goteborg")
    ap.add_argument("--evalset", type=Path, default=ROOT / "eval" / "evalset.jsonl")
    ap.add_argument("--out", type=Path, default=ROOT / "eval" / "results" / "answers.json")
    args = ap.parse_args()

    settings = get_settings()
    base = settings.ollama_base_url.rstrip("/")
    corpus = load_corpus(args.pdf_dir)
    spans = section_spans(corpus)
    questions = [json.loads(ln) for ln in args.evalset.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if args.limit:
        answerable = [q for q in questions if q["answerable"]][: args.limit]
        questions = answerable + [q for q in questions if not q["answerable"]][: max(2, args.limit // 4)]

    embedder = build_embedder(settings)
    pool = db.create_pool(settings.database_url)
    owner = f"eval-{uuid.uuid4()}"
    results: dict = {}
    try:
        ids = index(pool, embedder, corpus, owner, settings.strip_page_boilerplate,
                    settings.chunk_size, settings.chunk_overlap, settings.doc_header)
        name_of = {v: k for k, v in ids.items()}

        for model in args.models:
            unload_all(base)
            llm = OllamaLlm(base, model, settings.llm_timeout_seconds)
            runs = []
            for q in questions:
                t = time.perf_counter()
                ans = answer_question(pool=pool, embedder=embedder, llm=llm, settings=settings,
                                      owner_id=owner, question=q["question"])
                dt = time.perf_counter() - t
                runs.append({"q": q, "answer": ans.answer, "grounded": ans.grounded, "seconds": dt,
                             "sources": [(name_of[h.document_id], h.page, h.content) for h in ans.sources]})
                print(f"  {model} {q['id']} {dt:5.1f}s {'nej-svar' if not ans.grounded else 'svar'}", flush=True)
            results[model] = {"vram_mib": vram_mib(), "runs": runs}
            print(f"== {model}: VRAM {results[model]['vram_mib']} MiB", flush=True)

        unload_all(base)
        for model, res in results.items():  # judge pass
            for r in res["runs"]:
                q = r["q"]
                refused = not r["grounded"]
                if not q["answerable"]:
                    r["correct"], r["cited_ok"], r["faithful"] = refused, None, None
                    continue
                good = {(f, p) for f, n in q["expected"] for p in spans[(f, n)]}
                cited = {int(m) for m in CITE.findall(r["answer"])}
                r["cited_ok"] = any(1 <= i <= len(r["sources"]) and r["sources"][i - 1][:2] in good for i in cited)
                if refused:
                    r["correct"], r["faithful"] = False, None
                    continue
                r["correct"] = (judge_correct(base, args.judge, q["question"], q["answer"], r["answer"])
                                if q.get("answer") else r["cited_ok"])
                r["faithful"] = judge_faithful(base, args.judge, r["answer"], [s[2] for s in r["sources"]])
    finally:
        with pool.connection() as conn:
            conn.execute("DELETE FROM rag.chunks WHERE owner_id = %s", (owner,))
        pool.close()

    summary = {}
    for model, res in results.items():
        runs = res["runs"]
        ans_ = [r for r in runs if r["q"]["answerable"]]
        neg = [r for r in runs if not r["q"]["answerable"]]
        lat = sorted(r["seconds"] for r in runs)
        given = [r for r in ans_ if r["grounded"]]
        summary[model] = {
            "correct_answerable": sum(bool(r["correct"]) for r in ans_) / len(ans_),
            "refused_unanswerable": sum(bool(r["correct"]) for r in neg) / len(neg),
            "cited_ok": sum(bool(r["cited_ok"]) for r in ans_) / len(ans_),
            "faithful": sum(bool(r["faithful"]) for r in given) / max(1, len(given)),
            "wrongly_refused": sum(not r["grounded"] for r in ans_) / len(ans_),
            "latency_median_s": lat[len(lat) // 2], "latency_p90_s": lat[int(len(lat) * 0.9)],
            "vram_mib": res["vram_mib"], "n_answerable": len(ans_), "n_unanswerable": len(neg),
        }
    args.out.write_text(json.dumps({"judge": args.judge, "summary": summary, "results": results},
                                   ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
