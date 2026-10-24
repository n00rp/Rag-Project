"""Index the HR library into a separate experiment database, for trying another embedding model.

From ai-service:
    python ../eval/hr_index.py --db rag_exp --model intfloat/multilingual-e5-base --dim 768
then
    python ../eval/hr_check.py --retrieval --set DATABASE_URL=postgresql://.../rag_exp EMBEDDING_MODEL=... EMBEDDING_DIM=768
The live database (384 dimensions) is not touched. Document ids are those of the running API, so hr_check finds them.
"""
import argparse
import glob
import json
import os
import sys
import time
import urllib.request
import uuid

import psycopg

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai-service"))
from app import db  # noqa: E402
from app.boilerplate import strip_repeated_lines  # noqa: E402
from app.chunking import add_header, chunk_pages, document_header, heading_style  # noqa: E402
from app.config import Settings  # noqa: E402
from app.embeddings import build_embedder  # noqa: E402
from app.pdf import extract_pages  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--dim", type=int, required=True)
    ap.add_argument("--api", default="http://localhost:8080/api/")
    a = ap.parse_args()

    base = Settings().database_url
    admin = base.rsplit("/", 1)[0] + "/postgres"
    with psycopg.connect(admin, autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (a.db,)).fetchone():
            conn.execute(f'CREATE DATABASE "{a.db}"')
    url = base.rsplit("/", 1)[0] + "/" + a.db
    settings = Settings(database_url=url, embedding_model=a.model, embedding_dim=a.dim)
    embedder = build_embedder(settings)
    db.init_schema(url, embedder.dim)
    pool = db.create_pool(url)

    ids = {d["fileName"]: d["id"] for d in json.load(urllib.request.urlopen(a.api + "documents"))}
    files = sorted(glob.glob(f"{ROOT}/data/hr/*.pdf") + glob.glob(f"{ROOT}/data/ab/*.pdf"))
    t0 = time.time()
    for f in files:
        name = os.path.basename(f)
        pages = extract_pages(open(f, "rb").read())
        header = document_header(pages)
        pages = strip_repeated_lines(pages)
        chunks = add_header(chunk_pages(pages, settings.chunk_size, settings.chunk_overlap, heading_style(pages)), header)
        db.replace_document_chunks(pool, "demo", uuid.UUID(ids[name]), chunks, embedder.embed_passages([c.text for c in chunks]))
        print(f"{name}: {len(chunks)} chunks  ({time.time() - t0:.0f} s)", flush=True)
    print("klart:", url)


if __name__ == "__main__":
    main()
