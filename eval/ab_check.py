"""HR questions on AB 25 and its comments, checked against fact patterns taken from the text (no LLM judge).

Runs through the running API (default http://localhost:8080) so it measures what a user gets.
    python eval/ab_check.py [--api URL] [--only AB25.pdf] [--json out.json]
A question passes when it is not refused and every pattern in `must` matches the answer.
`page` is where the fact sits in AB25.pdf; "found" tells whether a cited source is that page.
"""
import argparse
import json
import re
import urllib.request

# (question, [regex that must all match], page in AB25.pdf or None)
QUESTIONS = [
    ("Hur många semesterdagar har en medarbetare som fyller 45 år?", [r"\b31\b"], 45),
    ("Hur många semesterdagar får man till och med det år man fyller 39?", [r"\b25\b"], 45),
    ("Vad är uppsägningstiden om arbetsgivaren säger upp någon som varit anställd i över ett år?", [r"6 månader|sex månader"], 59),
    ("Hur lång uppsägningstid har en arbetstagare själv?", [r"3 månader|tre månader"], 59),
    ("Hur länge får en provanställning vara?", [r"6 (kalender)?månader|sex"], 8),
    ("Från vilken dag krävs läkarintyg vid sjukdom?", [r"7 kalenderdagar|sju"], 52),
    ("Hur stor är sjuklönen efter första 14 dagarna i en sjukperiod?", [r"10 procent|10 %"], 53),
    ("Hur länge kan man få föräldrapenningtillägg och hur stort är det?", [r"180", r"10 procent|10 %"], 55),
    ("Hur många dagar får man föräldralön?", [r"270"], 56),
    ("Hur lång är ordinarie arbetstid för en heltidsanställd?", [r"40 timmar"], 18),
    ("Hur mycket ledighet får man för en timmes enkel övertid?", [r"1 ?½|1 1⁄2|1,5|en och en halv"], 30),
    ("Hur många månader i förväg ska man anmäla föräldraledighet?", [r"3 månader|tre månader"], 56),
    ("Vad gäller för uppsägningstid för en 62-åring som sagts upp på grund av arbetsbrist och varit anställd i 12 år?", [r"ett år|12 månader"], 59),
    ("Vilken extra kompensation får den som får semester utanför juni–augusti?", [r"5000|3000"], 45),
    ("Hur många timmar övertidsledighet får man spara?", [r"200"], 31),
    ("Kan arbetsgivaren stänga av en arbetstagare som misstänks för brott?", [r"avstäng|ta ur arbete|tillfälligt"], 13),
]


def post(api, path, body):
    req = urllib.request.Request(api + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=300))


def direct_runner(overrides):
    """Run retrieval + answer in this process (cd ai-service; use its venv) so settings can be overridden."""
    import sys
    sys.path.insert(0, "../ai-service" if __import__("os").path.isdir("../ai-service") else "ai-service")
    from app import db, rag
    from app.config import Settings
    from app.embeddings import build_embedder
    from app.llm import build_llm

    settings = Settings(**overrides)
    pool, embedder, llm = db.create_pool(settings.database_url), build_embedder(settings), build_llm(settings)

    def ask(question, doc_ids):
        import uuid
        a = rag.answer_question(llm=llm, pool=pool, embedder=embedder, settings=settings, owner_id="demo",
                                question=question, document_ids=[uuid.UUID(i) for i in doc_ids])
        return {"answer": a.answer, "grounded": a.grounded,
                "sources": [{"documentId": str(h.document_id), "page": h.page} for h in a.sources]}
    return ask


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--direct", action="store_true", help="run in-process instead of through the API")
    ap.add_argument("--set", nargs="*", default=[], help="settings overrides for --direct, NAME=VALUE")
    ap.add_argument("--api", default="http://localhost:8080/api/")
    ap.add_argument("--only", nargs="*", default=["AB25.pdf", "AB25-kommentarer.pdf"], help="file names to search in")
    ap.add_argument("--json")
    a = ap.parse_args()
    docs = json.load(urllib.request.urlopen(a.api + "documents"))
    ids = {d["fileName"]: d["id"] for d in docs}
    doc_ids = [ids[n] for n in a.only]
    ab_id = ids["AB25.pdf"]
    ask = direct_runner({k.lower(): v for k, v in (x.split("=", 1) for x in a.set)}) if a.direct else None
    rows, ok = [], 0
    for q, must, page in QUESTIONS:
        r = ask(q, doc_ids) if ask else post(a.api, "chat", {"question": q, "documentIds": doc_ids})
        ans = r["answer"]
        refused = not r.get("grounded", True)
        hit = all(re.search(m, ans, re.I) for m in must) and not refused
        found = any(s["documentId"] == ab_id and s["page"] == page for s in r.get("sources", []))
        ok += hit
        rows.append({"q": q, "pass": hit, "refused": refused, "source_page_found": found, "answer": ans})
        print(("OK  " if hit else "FEL ") + ("[källa ok] " if found else "[källa saknas] ") + q)
        if not hit:
            print("      ->", ans[:220].replace("\n", " "))
    print(f"\n{ok} av {len(QUESTIONS)} svar innehåller rätt fakta")
    if a.json:
        json.dump(rows, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
