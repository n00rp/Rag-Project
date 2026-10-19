"""Writes eval/review/evalset-review.md: every question with its reference answer and the section it points at,
so a person can check the eval set quickly. Tick one box per question; apply_review.py reads the result.

    ai-service/.venv/Scripts/python eval/make_review.py
"""

import json
import re
import sys
from pathlib import Path

from sections import load_sections

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EGNA_MARKER = "<!-- EGNA FRÅGOR NEDAN -->"


def main() -> None:
    sections = {(s.file, s.number): s for s in load_sections(ROOT / "data" / "goteborg")}
    decisions = {}
    decision_file = HERE / "review" / "decisions.json"
    if decision_file.exists():
        decisions = json.loads(decision_file.read_text(encoding="utf-8")).get("decisions", {})
    rows = [json.loads(line) for line in (HERE / "evalset.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

    out = [
        "# Granska evalsetet", "",
        "Gå igenom frågorna uppifrån och ned. Sätt ett `x` i EN ruta per fråga:", "",
        "- **stämmer**: frågan är rimlig, facit stämmer och rätt källa är rätt.",
        "- **ändra**: skriv den rättade frågan och/eller facit på raderna `Ny fråga:` och `Nytt facit:` (lämna tomt det som är rätt).",
        "- **ta bort**: frågan är dålig, tvetydig eller fel.", "",
        "Frågor som redan är bedömda i en tidigare omgång är förifyllda. Du kan lägga till egna frågor sist i filen under",
        "rubriken `# Egna frågor` (en per rad).", "",
        "Rätt källa visas med ärendets rubrik och sidor så att du kan slå upp den i PDF:en.", "",
    ]
    for typ in sorted({r["type"] for r in rows}):
        group = [r for r in rows if r["type"] == typ]
        out += [f"# {typ} ({len(group)})", ""]
        for r in group:
            tick = decisions.get(r["id"], {}).get("verdict", "")
            box = lambda name: f"[{'x' if tick == name else ' '}] {name}"  # noqa: E731
            out += [f"## {r['id']} · {r['split']} · {r['source']}", "", f"**Fråga:** {r['question']}", ""]
            if r["answerable"]:
                out += [f"**Facit:** {r.get('answer') or '(inget facit, bara rätt källa)'}", ""]
                for f, n in r["expected"][:4]:
                    s = sections.get((f, n))
                    where = f"{f[:-4]} § {n}" + (f" (s. {s.first_page}–{s.last_page}): {s.title[:110]}" if s else "")
                    out.append(f"- Rätt källa: {where}")
                if len(r["expected"]) > 4:
                    out.append(f"- … och {len(r['expected']) - 4} till")
                out.append("")
            else:
                out += ["**Facit:** ska nekas (inget stöd i dokumenten)", ""]
            out += [f"- {box('stämmer')}   - {box('ändra')}   - {box('ta bort')}   `id={r['id']}`", "",
                    "Ny fråga: ", "Nytt facit: ", ""]
    out += ["# Egna frågor", "",
            "Skriv en fråga per rad på formen `Fråga | facit (kort) | dokument och § om du vet` under markören nedan.",
            "Dokument skrivs som KS0409, KS0611, KS1126, KS2411, KF24 eller KF25, till exempel `KS0409 § 317`.",
            "Utan dokument och § kan frågan inte räknas i sökmåtten förrän jag lagt till den.", "",
            EGNA_MARKER, "", ""]
    path = HERE / "review" / "evalset-review.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and "--force" not in sys.argv:
        old = path.read_text(encoding="utf-8")
        if re.search(r"\[[xX]\]", old) or EGNA_MARKER + "\n" in old and old.split(EGNA_MARKER)[1].strip():
            raise SystemExit(f"{path.name} innehåller redan markeringar eller egna frågor. Kör apply_review.py först "
                             "(de sparas då i decisions.json) eller använd --force för att skriva över.")
    path.write_text("\n".join(out), encoding="utf-8")
    print(f"{len(rows)} frågor skrivna till {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
