import psycopg
import pytest

from app import db


@pytest.fixture
def scratch_url(database_url):
    """An empty database of its own: the migration drops a table, which must never touch the dev data."""
    base = database_url.rsplit("/", 1)[0]
    name = "rag_test_schema_dim"
    with psycopg.connect(base + "/postgres", autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}"')
        conn.execute(f'CREATE DATABASE "{name}"')
    yield f"{base}/{name}"
    with psycopg.connect(base + "/postgres", autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}"')


def test_another_vector_dimension_is_refused_unless_a_reset_is_asked_for(scratch_url):
    db.init_schema(scratch_url, 8)
    db.init_schema(scratch_url, 8)  # same dimension: idempotent
    with psycopg.connect(scratch_url, autocommit=True) as conn:
        conn.execute("INSERT INTO rag.chunks (owner_id, document_id, page, chunk_index, content, embedding) "
                     "VALUES ('o', gen_random_uuid(), 1, 0, 'text', %s::vector)", ("[" + ",".join(["0.1"] * 8) + "]",))

    with pytest.raises(RuntimeError, match="RESET_VECTORS_ON_DIM_CHANGE"):
        db.init_schema(scratch_url, 16)
    with psycopg.connect(scratch_url) as conn:
        assert conn.execute("SELECT count(*) FROM rag.chunks").fetchone()[0] == 1  # refusing left the data alone

    db.init_schema(scratch_url, 16, reset_on_dim_change=True)
    with psycopg.connect(scratch_url) as conn:
        assert conn.execute("SELECT count(*) FROM rag.chunks").fetchone()[0] == 0
