"""Runs the HR questions in eval/hr_questions.py against the document library and checks the answers against facts.

From ai-service (uses its venv):
    python ../eval/hr_check.py --verify            # only check that every fact is in its source and every "absent" word is absent
    python ../eval/hr_check.py                     # ask through the running API (http://localhost:8080/api/)
    python ../eval/hr_check.py --direct --set TOP_K=8 LLM_BACKEND=ollama LLM_MODEL=gemma3:12b OLLAMA_BASE_URL=...
    python ../eval/hr_check.py --json out.json     # keep every answer

No LLM judge: an answer passes when it is not a refusal and every pattern matches. A question without patterns passes when
the answer is a refusal. Every third question is the `test` split; tune on `dev`, look at `test` when deciding.
"""
import argparse
import glob
import json
import os
import re
import sys
import time
import urllib.request
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai-service"))
sys.path.insert(0, os.path.dirname(__file__))
import importlib  # noqa: E402

# --questions=hr_colloquial picks another question file in this folder (read before argparse so the module-level name exists)
QUESTIONS = importlib.import_module(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--questions=")), "hr_questions")).QUESTIONS

ROOT = os.path.join(os.path.dirname(__file__), "..")


def split(i: int) -> str:
    return "test" if i % 3 == 2 else "dev"


def library_files() -> list[str]:
    return sorted(glob.glob(f"{ROOT}/data/hr/*.pdf") + glob.glob(f"{ROOT}/data/ab/*.pdf"))


def verify() -> int:
    from app.pdf import extract_pages

    texts = {os.path.basename(f): re.sub(r"\s+", " ", " ".join(p.text for p in extract_pages(open(f, "rb").read()))) for f in library_files()}
    problems = 0
    for topic, q, must, src, absent in QUESTIONS:
        hits = [t for name, t in texts.items() if name.startswith(src)] if src else []
        if must:
            if not hits:
                print(f"SAKNAR KÄLLA {src!r}: {q}")
                problems += 1
            for m in must:
                if not any(re.search(m, t) for t in hits):
                    print(f"FAKTA SAKNAS i {src}: {m!r}  <- {q}")
                    problems += 1
        for term in absent:
            where = [name for name, t in texts.items() if term.lower() in t.lower()]
            if where:
                print(f"ORDET FINNS: {term!r} i {where[:3]}  <- {q}")
                problems += 1
    print(f"{len(QUESTIONS)} frågor kontrollerade mot {len(texts)} dokument, {problems} problem")
    return problems


def direct_runner(overrides, names):
    import uuid

    from app import db, rag
    from app.config import Settings
    from app.embeddings import build_embedder
    from app.llm import build_llm

    settings = Settings(**overrides)
    pool, embedder, llm = db.create_pool(settings.database_url), build_embedder(settings), build_llm(settings)

    def ask(question, doc_ids):
        a = rag.answer_question(llm=llm, pool=pool, embedder=embedder, settings=settings, owner_id="demo",
                                question=question, document_ids=[uuid.UUID(i) for i in doc_ids])
        return {"answer": a.answer, "grounded": a.grounded, "sources": [{"fileName": names.get(str(h.document_id), "")} for h in a.sources]}
    return ask


def retrieval_only(a) -> None:
    """Share of answerable questions whose fact patterns all match the text of the retrieved chunks, plus how often a
    chunk of the expected source is among them, and how many unanswerable questions the service refuses outright."""
    import uuid

    from app import db, rag
    from app.config import Settings
    from app.embeddings import build_embedder
    from app.llm import build_llm

    settings = Settings(**{k.lower(): v for k, v in (x.split("=", 1) for x in a.set)})
    pool, embedder = db.create_pool(settings.database_url), build_embedder(settings)
    llm = build_llm(settings) if settings.rewrite_query else None
    names = {os.path.basename(f) for f in library_files()}
    docs = json.load(urllib.request.urlopen(a.api + "documents"))
    ids = [uuid.UUID(d["id"]) for d in docs if d["fileName"] in names]
    file_of = {d["id"]: d["fileName"] for d in docs}
    rows = []
    for i, (topic, q, must, src, _absent) in enumerate(QUESTIONS):
        r = rag.retrieve(pool=pool, embedder=embedder, settings=settings, owner_id="demo", question=q, document_ids=ids, llm=llm)
        text = " ".join(re.sub(r"\s+", " ", h.content) for h in r.hits)
        rows.append({"i": i, "topic": topic, "split": split(i), "q": q, "answerable": bool(must), "refused": r.refused,
                     "evidence": bool(must) and all(re.search(m, text, re.I) for m in must),
                     "source": bool(src) and any(src.lower() in file_of[str(h.document_id)].lower() for h in r.hits)})
    ans = [r for r in rows if r["answerable"]]
    for label, sel in [("alla", ans), ("dev", [r for r in ans if r["split"] == "dev"]), ("test", [r for r in ans if r["split"] == "test"])]:
        print(f"{label:5s} faktan i träffarna {sum(r['evidence'] for r in sel)}/{len(sel)}   rätt dokument bland träffarna {sum(r['source'] for r in sel)}/{len(sel)}   nekas av sökningen {sum(r['refused'] for r in sel)}")
    un = [r for r in rows if not r["answerable"]]
    print(f"saknar svar: nekas av sökningen {sum(r['refused'] for r in un)}/{len(un)}")
    by = defaultdict(list)
    for r in ans:
        by[r["topic"]].append(r)
    print("fakta i träffarna per område:", "  ".join(f"{t} {sum(x['evidence'] for x in v)}/{len(v)}" for t, v in by.items()))
    if a.json:
        json.dump(rows, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def post(api, path, body):
    req = urllib.request.Request(api + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=300))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default="hr_questions", help="module in eval/ with a QUESTIONS list (use --questions=NAME)")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--api", default="http://127.0.0.1:8080/api/")
    ap.add_argument("--direct", action="store_true")
    ap.add_argument("--set", nargs="*", default=[], help="settings overrides for --direct, NAME=VALUE")
    ap.add_argument("--retrieval", action="store_true", help="no LLM: is the fact in the retrieved chunks? (implies --direct)")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.verify:
        sys.exit(1 if verify() else 0)

    if a.retrieval:
        return retrieval_only(a)
    names = {os.path.basename(f) for f in library_files()}
    docs = json.load(urllib.request.urlopen(a.api + "documents"))
    doc_ids = [d["id"] for d in docs if d["fileName"] in names]
    ask = direct_runner({k.lower(): v for k, v in (x.split("=", 1) for x in a.set)}, {d["id"]: d["fileName"] for d in docs}) if a.direct else None
    print(f"{len(doc_ids)} dokument i biblioteket, {len(QUESTIONS)} frågor")

    rows = []
    for i, (topic, q, must, src, _absent) in enumerate(QUESTIONS[: a.limit]):
        t0 = time.time()
        r = ask(q, doc_ids) if ask else post(a.api, "chat", {"question": q, "documentIds": doc_ids})
        grounded = r.get("grounded", True)
        ok = (not grounded) if not must else (grounded and all(re.search(m, r["answer"], re.I) for m in must))
        cited = bool(src) and any(src.lower() in s["fileName"].lower() for s in r.get("sources", []))
        rows.append({"i": i, "topic": topic, "split": split(i), "q": q, "pass": ok, "refusal_expected": not must,
                     "grounded": grounded, "source_ok": cited, "seconds": round(time.time() - t0, 1), "answer": r["answer"]})
        print(("OK  " if ok else "FEL ") + f"[{topic}] {q}")
        if not ok:
            print("      ->", r["answer"][:230].replace("\n", " "))

    def rate(sel):
        return f"{sum(r['pass'] for r in sel)}/{len(sel)}" if sel else "-"

    print("\n=== Sammanfattning")
    answerable = [r for r in rows if not r["refusal_expected"]]
    for label, sel in [("besvarbara", answerable), ("  dev", [r for r in answerable if r["split"] == "dev"]),
                       ("  test", [r for r in answerable if r["split"] == "test"]),
                       ("saknar svar (ska nekas)", [r for r in rows if r["refusal_expected"]])]:
        print(f"{label:28s} {rate(sel)}")
    print(f"{'rätt källa citerad':28s} {sum(r['source_ok'] for r in answerable)}/{len(answerable)}")
    by = defaultdict(list)
    for r in rows:
        by[r["topic"]].append(r)
    print("per område:", "  ".join(f"{t} {rate(v)}" for t, v in by.items()))
    if a.json:
        json.dump(rows, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
