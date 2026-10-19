import os
import uuid

os.environ.setdefault("EMBEDDING_BACKEND", "fake")
os.environ.setdefault("LLM_BACKEND", "fake")
os.environ.setdefault("INTERNAL_API_KEY", "")
# The fake embedder has its own score scale; the real threshold is tuned on e5 in eval/README.md.
os.environ.setdefault("MIN_SCORE", "0")

import psycopg
import pytest
from fastapi.testclient import TestClient
from fpdf import FPDF

from app.config import get_settings


def make_pdf(pages: list[str]) -> bytes:
    pdf = FPDF()
    pdf.set_font("Helvetica", size=12)
    for text in pages:
        pdf.add_page()
        pdf.multi_cell(0, 8, text)
    return bytes(pdf.output())


@pytest.fixture(scope="session")
def database_url() -> str:
    url = get_settings().database_url
    try:
        psycopg.connect(url, connect_timeout=3).close()
    except psycopg.OperationalError:
        pytest.skip("Postgres är inte tillgänglig (kör: docker compose up -d db)")
    return url


@pytest.fixture(scope="session")
def client(database_url):
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def _owners(database_url):
    """Owners created during the run; their chunks are removed at the end so the dev database does not fill up."""
    names: list[str] = []
    yield names
    with psycopg.connect(database_url) as conn:
        conn.execute("DELETE FROM rag.chunks WHERE owner_id = ANY(%s)", (names,))


@pytest.fixture
def owner(_owners) -> str:
    name = f"test-{uuid.uuid4()}"
    _owners.append(name)
    return name
