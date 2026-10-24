"""Download the HR sources into data/hr/ (git-ignored): laws from riksdagen.se, AB 25 with comments and annexes from SKR.

    python scripts/fetch_hr_docs.py            # fetch what is missing
    python scripts/fetch_hr_docs.py --seed     # also upload everything to the running API (http://localhost:8080)

The app reads PDFs only, so each law (consolidated HTML text from data.riksdagen.se) is printed to PDF with headless
Chrome/Edge. Page numbers in citations are therefore those of that printout, not of an official PDF.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "data" / "hr"
SKR = "https://skr.se/download/"

# SFS number -> (file name, abbreviation people use). The abbreviation is printed above the law so that the document
# header of every chunk contains it: questions say "LAS", the law's own title says "lag om anställningsskydd".
LAWS = {
    "1982:80": ("LAS_lag-om-anstallningsskydd", "LAS"),
    "1977:480": ("Semesterlag", "SemL"),
    "1976:580": ("MBL_medbestammandelagen", "MBL"),
    "1982:673": ("Arbetstidslag", "ATL"),
    "1977:1160": ("Arbetsmiljolag", "AML"),
    "2008:567": ("Diskrimineringslag", "DL"),
    "1991:1047": ("Sjuklonelag", "SjLL"),
    "1995:584": ("Foraldraledighetslag", "FörL"),
    "1994:260": ("LOA_lag-om-offentlig-anstallning", "LOA"),
    "1974:358": ("Lag-om-facklig-fortroendemans-stallning", "FML"),
    "2021:890": ("Visselblasarlag", "Visselblåsarlagen"),
    "1974:981": ("Studieledighetslag", "Studieledighetslagen"),
}
SKR_PDFS = {
    "AB25-redogorelsetext.pdf": "18.1adb2f31199a33736313226/1759391207939/Redogorelsetext-allmanna-bestammelser-AB-25-och-bilagor-till-AB.pdf",
    "AB25-bilaga-M-larare.pdf": "18.4d2a888c19913a970f86c663/1757404111873/Bilaga%20M-25.pdf",
    "AB25-bilaga-J-jour.pdf": "18.4d2a888c19913a970f86c662/1757404111730/Bilaga-J-i-lydelse-2024-04-01-korr.pdf",
    "AB25-bilaga-R.pdf": "18.4d2a888c19913a970f86c661/1757404111635/Bilaga-R-i-lydelse-2025-04-01.pdf",
    "AB25-bilaga-D-personalpool.pdf": "18.4d2a888c19913a970f86c660/1757404111544/Bilaga-D-i-lydelse-2025-04-01.pdf",
    "AB25-bilaga-U-uppehallsanstallning.pdf": "18.2a18bd5d19a0f669b7625e6e/1761316580231/Bilaga-U-till-AB-i-lydelse-2025-04-01-251023.pdf",
    "AB25-specialbestammelser-lakare.pdf": "18.7767e49f199a325d96e24806/1759501577509/Specialbestammelser-for-lakare-och-med-stud-25.pdf",
}
CSS = "<meta charset='utf-8'><style>body{font:11pt/1.35 Georgia,serif;margin:0 1cm}h1,h2,h3{font-family:Arial,sans-serif}</style>"


def get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=120) as r:
        return r.read()


def browser() -> str:
    for candidate in (os.environ.get("CHROME"), shutil.which("chrome"), shutil.which("msedge"),
                      r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                      r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"):
        if candidate and Path(candidate).exists():
            return candidate
    sys.exit("Hittar ingen Chrome/Edge. Sätt miljövariabeln CHROME till sökvägen.")


def law_pdf(sfs: str, short: str, out: Path) -> None:
    html = get(f"https://data.riksdagen.se/dokument/sfs-{sfs.replace(':', '-')}.html").decode("utf-8")
    html = re.sub(r"<style.*?</style>", "", html, flags=re.S | re.I)
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "law.html"
        page.write_text(CSS + f"<p><b>Förkortning: {short}</b></p>" + html, encoding="utf-8")
        subprocess.run([browser(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={out}", page.as_uri()], check=True, capture_output=True, timeout=120)


def seed(api: str) -> None:
    have = {d["fileName"] for d in json.load(urllib.request.urlopen(api + "/api/documents"))}
    for pdf in sorted(TARGET.glob("*.pdf")) + sorted((ROOT / "data" / "ab").glob("*.pdf")):
        if pdf.name in have:
            continue
        boundary = uuid.uuid4().hex
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{pdf.name}"\r\n'
                f"Content-Type: application/pdf\r\n\r\n").encode() + pdf.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(api + "/api/documents", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})
        print("uppladdad", pdf.name, json.load(urllib.request.urlopen(req))["status"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true")
    ap.add_argument("--api", default="http://localhost:8080")
    a = ap.parse_args()
    TARGET.mkdir(parents=True, exist_ok=True)
    for sfs, (name, short) in LAWS.items():
        out = TARGET / f"{name}_SFS-{sfs.replace(':', '-')}.pdf"
        if not out.exists():
            law_pdf(sfs, short, out)
        print("ok", out.name, f"{out.stat().st_size // 1024} kB")
    for name, path in SKR_PDFS.items():
        out = TARGET / name
        if not out.exists():
            out.write_bytes(get(SKR + path))
        print("ok", out.name, f"{out.stat().st_size // 1024} kB")
    if a.seed:
        seed(a.api)


if __name__ == "__main__":
    main()
