"""Records a demo session: real answers to a fixed set of questions, saved to frontend/public/demo-session.json.

The app shows it when the AI model is offline (and from the command palette), so someone without access to the GPU
machine can still see what an answer looks like. It talks to the AI service directly (port 8000), so nothing is
added to anyone's chat history; file names come from the API (port 8080). Needs the stack running with the demo
documents indexed (python scripts/demo_docs.py seed).

    python scripts/record_demo_session.py
"""

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "frontend" / "public" / "demo-session.json"
AI = "http://127.0.0.1:8000"
API = "http://127.0.0.1:8080"

QUESTIONS = [
    "Vad beslutade kommunstyrelsen om investeringar i europeisk försvarsindustri?",
    "Vem anmälde jäv vid sammanträdet 2025-04-09?",
    "Vad behandlades under § 319 i kommunstyrelsens protokoll från 2025-04-09?",
    "Vad gäller ärende SLK-2025-00392?",
    "Ge en överblick över besluten om politiska sekreterare.",
    "Vad gäller ärende SLK-2030-00001?",
]


def post_json(url: str, body: dict) -> dict:
    request = urllib.request.Request(url, json.dumps(body).encode("utf-8"), {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)


def env_value(name: str) -> str:
    env = ROOT / ".env"
    if env.exists():
        match = re.search(rf"^{name}=(.*)$", env.read_text(encoding="utf-8"), re.M)
        if match:
            return match.group(1).strip()
    return ""


def main() -> None:
    with urllib.request.urlopen(f"{API}/api/documents", timeout=30) as response:
        names = {d["id"]: d["fileName"] for d in json.load(response)}
    if not names:
        sys.exit("Inga dokument är uppladdade: kör python scripts/demo_docs.py seed först.")

    recorded = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    turns = []
    for i, question in enumerate(QUESTIONS, 1):
        answer = post_json(f"{AI}/query", {"owner_id": "demo", "question": question})
        turns.append({
            "id": f"demo-{i}", "question": question, "answer": answer["answer"], "grounded": answer["grounded"],
            "support": answer.get("support", "fullt"), "broad": answer.get("broad", False), "createdAt": recorded,
            "sources": [{"documentId": s["document_id"], "fileName": names.get(s["document_id"], "okänt dokument"),
                         "page": s["page"], "snippet": s["snippet"], "score": s["score"]} for s in answer["sources"]],
        })
        print(f"{i}/{len(QUESTIONS)} {question[:60]}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"recordedAt": recorded, "model": env_value("LLM_MODEL") or "okänd", "turns": turns},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Sparade {len(turns)} svar i {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
