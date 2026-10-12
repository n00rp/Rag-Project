from dataclasses import dataclass
from uuid import UUID

import numpy as np
import psycopg
from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

from app.chunking import Chunk


@dataclass(frozen=True)
class Hit:
    document_id: UUID
    page: int
    chunk_index: int
    content: str
    score: float  # cosine similarity, higher is better


def init_schema(database_url: str, dim: int) -> None:
    """Idempotent. Runs on a plain connection because the vector type must exist before registering it."""
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.execute("CREATE SCHEMA IF NOT EXISTS rag")
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS rag.chunks (
                id          bigserial PRIMARY KEY,
                owner_id    text        NOT NULL,
                document_id uuid        NOT NULL,
                page        integer     NOT NULL,
                chunk_index integer     NOT NULL,
                content     text        NOT NULL,
                embedding   vector({dim}) NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS chunks_owner_doc ON rag.chunks (owner_id, document_id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw "
            "ON rag.chunks USING hnsw (embedding vector_cosine_ops)"
        )


def create_pool(database_url: str) -> ConnectionPool:
    pool = ConnectionPool(database_url, min_size=1, max_size=5, configure=register_vector, open=False)
    pool.open(wait=True, timeout=15)
    return pool


def replace_document_chunks(
    pool: ConnectionPool, owner_id: str, document_id: UUID, chunks: list[Chunk], embeddings: np.ndarray
) -> None:
    """Re-ingesting a document replaces its chunks atomically."""
    with pool.connection() as conn, conn.transaction():
        conn.execute(
            "DELETE FROM rag.chunks WHERE owner_id = %s AND document_id = %s", (owner_id, document_id)
        )
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO rag.chunks (owner_id, document_id, page, chunk_index, content, embedding) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                [
                    (owner_id, document_id, c.page, c.index, c.text, emb)
                    for c, emb in zip(chunks, embeddings, strict=True)
                ],
            )


def search(
    pool: ConnectionPool,
    owner_id: str,
    query_embedding: np.ndarray,
    top_k: int,
    document_ids: list[UUID] | None = None,
) -> list[Hit]:
    """owner_id is mandatory and always part of the WHERE clause: this is the data-isolation boundary."""
    sql = (
        "SELECT document_id, page, chunk_index, content, 1 - (embedding <=> %(q)s) AS score "
        "FROM rag.chunks WHERE owner_id = %(owner)s "
    )
    params: dict = {"q": query_embedding, "owner": owner_id, "k": top_k}
    if document_ids:
        sql += "AND document_id = ANY(%(docs)s) "
        params["docs"] = document_ids
    sql += "ORDER BY embedding <=> %(q)s LIMIT %(k)s"
    with pool.connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [Hit(*row) for row in rows]


def delete_document(pool: ConnectionPool, owner_id: str, document_id: UUID) -> int:
    with pool.connection() as conn:
        cur = conn.execute(
            "DELETE FROM rag.chunks WHERE owner_id = %s AND document_id = %s", (owner_id, document_id)
        )
        return cur.rowcount
