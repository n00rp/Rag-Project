"""Fetch the demo document collection and load it into a running API.

    python scripts/demo_docs.py fetch              # download the PDFs listed in demo-docs.json
    python scripts/demo_docs.py seed               # upload them to the API (skips ones already there)
    python scripts/demo_docs.py seed --api http://localhost:8080

The PDFs are public records from Göteborgs Stad. They are downloaded to data/goteborg/ (git-ignored)
rather than committed, so every machine gets the same collection without redistributing the files.
Standard library only, so it runs on any machine with Python 3.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "scripts" / "demo-docs.json"
TARGET = ROOT / "data" / "goteborg"
USER_AGENT = "kommunkoll-demo-fetch/1.0 (portfolio project)"


def load_manifest() -> list[dict]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["documents"]


def fetch() -> int:
    TARGET.mkdir(parents=True, exist_ok=True)
    failed = 0
    for doc in load_manifest():
        path = TARGET / doc["file"]
        if path.exists():
            print(f"= {doc['file']} (finns redan)")
            continue
        try:
            request = urllib.request.Request(doc["url"], headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"! {doc['file']}: kunde inte hämtas ({exc})")
            failed += 1
            continue
        if not data.startswith(b"%PDF-"):
            print(f"! {doc['file']}: svaret var ingen PDF, hoppar över")
            failed += 1
            continue
        path.write_bytes(data)
        print(f"+ {doc['file']} ({len(data) / 1024:.0f} kB)")
    return 1 if failed else 0


def _multipart(filename: str, data: bytes) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    # RFC 5987 so non-ASCII file names (Å, Ä, Ö) survive.
    quoted = urllib.parse.quote(filename)
    head = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"file\"; filename=\"{quoted}\"; filename*=UTF-8''{quoted}\r\n"
        "Content-Type: application/pdf\r\n\r\n"
    ).encode()
    return head + data + f"\r\n--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"


def seed(api: str) -> int:
    api = api.rstrip("/")
    try:
        with urllib.request.urlopen(f"{api}/api/documents", timeout=15) as response:
            existing = {d["fileName"] for d in json.load(response)}
    except urllib.error.URLError as exc:
        print(f"Kan inte nå API:et på {api}: {exc}")
        return 1

    files = sorted(TARGET.glob("*.pdf"))
    if not files:
        print("Inga PDF:er i data/goteborg. Kör först: python scripts/demo_docs.py fetch")
        return 1

    failed = 0
    for path in files:
        if path.name in existing:
            print(f"= {path.name} (finns redan)")
            continue
        body, content_type = _multipart(path.name, path.read_bytes())
        request = urllib.request.Request(
            f"{api}/api/documents", data=body, method="POST", headers={"Content-Type": content_type}
        )
        try:
            urllib.request.urlopen(request, timeout=120).close()
            print(f"+ {path.name}")
        except urllib.error.HTTPError as exc:
            print(f"! {path.name}: {exc.code} {exc.read().decode(errors='replace')[:200]}")
            failed += 1
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch", help="download the demo PDFs")
    seed_parser = sub.add_parser("seed", help="upload the demo PDFs to the API")
    seed_parser.add_argument("--api", default="http://localhost:5174", help="API base URL (default: %(default)s)")
    args = parser.parse_args()
    return fetch() if args.command == "fetch" else seed(args.api)


if __name__ == "__main__":
    sys.exit(main())
