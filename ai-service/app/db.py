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
    # Set by the hybrid search: the chunk contains the question's rare words (e.g. a case number), so it is
    # a hit by name and not only by similarity; the "no support" threshold must not apply to it.
    matched: bool = False
    # What the model reads when that is more than the excerpt: the chunk plus its neighbours on the same page.
    context: str | None = None


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
        # Full-text side of the hybrid search (case numbers, section numbers, names). Generated from content, so
        # existing rows get it too and there is nothing to keep in sync.
        conn.execute(
            "ALTER TABLE rag.chunks ADD COLUMN IF NOT EXISTS content_tsv tsvector "
            "GENERATED ALWAYS AS (to_tsvector('swedish', content)) STORED"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS chunks_content_tsv ON rag.chunks USING gin (content_tsv)")


def create_pool(database_url: str) -> ConnectionPool:
    pool = ConnectionPool(database_url, min_size=1, max_size=5, configure=register_vector, open=False)
    pool.open(wait=True, timeout=15)
    return pool


# owner -> (document frequency per stemmed word, number of chunks). Rebuilt after every ingest or delete.
_word_stats: dict[str, tuple[dict[str, int], int]] = {}


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
    _word_stats.pop(owner_id, None)


def _filters(owner_id: str, document_ids: list[UUID] | None, content_contains: list[str] | None) -> tuple[str, dict]:
    sql = "owner_id = %(owner)s "
    params: dict = {"owner": owner_id}
    if document_ids:
        sql += "AND document_id = ANY(%(docs)s) "
        params["docs"] = document_ids
    if content_contains:
        sql += "AND content LIKE ALL(%(like)s) "
        params["like"] = ["%" + s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%" for s in content_contains]
    return sql, params


def search(
    pool: ConnectionPool,
    owner_id: str,
    query_embedding: np.ndarray,
    top_k: int,
    document_ids: list[UUID] | None = None,
    content_contains: list[str] | None = None,
) -> list[Hit]:
    """owner_id is mandatory and always part of the WHERE clause: this is the data-isolation boundary.
    content_contains: only chunks whose text contains every one of these strings (e.g. the meeting date)."""
    where, params = _filters(owner_id, document_ids, content_contains)
    sql = (
        "SELECT document_id, page, chunk_index, content, 1 - (embedding <=> %(q)s) AS score "
        f"FROM rag.chunks WHERE {where}ORDER BY embedding <=> %(q)s LIMIT %(k)s"
    )
    params |= {"q": query_embedding, "k": top_k}
    with pool.connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [Hit(*row) for row in rows]


def contains_any(
    pool: ConnectionPool, owner_id: str, patterns: list[str], document_ids: list[UUID] | None = None
) -> bool:
    """True if some chunk matches at least one of the (case-insensitive POSIX) patterns."""
    where, params = _filters(owner_id, document_ids, None)
    params["patterns"] = patterns
    with pool.connection() as conn:
        return conn.execute(
            f"SELECT EXISTS (SELECT 1 FROM rag.chunks WHERE {where}AND content ~* ANY(%(patterns)s))", params
        ).fetchone()[0]


def _stats(pool: ConnectionPool, owner_id: str) -> tuple[dict[str, int], int]:
    if owner_id not in _word_stats:
        with pool.connection() as conn:
            total = conn.execute("SELECT count(*) FROM rag.chunks WHERE owner_id = %s", (owner_id,)).fetchone()[0]
            # ts_stat takes a query as text; owner_id is bound to the quoted literal by the driver.
            literal = conn.execute("SELECT quote_literal(%s)", (owner_id,)).fetchone()[0]
            rows = conn.execute(
                "SELECT word, ndoc FROM ts_stat('SELECT content_tsv FROM rag.chunks WHERE owner_id = ' || %s)",
                (literal,),
            ).fetchall()
        _word_stats[owner_id] = (dict(rows), total)
    return _word_stats[owner_id]


HYBRID_SQL = """
WITH vec AS (
    SELECT id, row_number() OVER (ORDER BY embedding <=> %(q)s) AS r FROM rag.chunks
    WHERE {where} ORDER BY embedding <=> %(q)s LIMIT %(pool)s
), fts AS (
    SELECT id, row_number() OVER (ORDER BY ts_rank_cd(content_tsv, query) DESC) AS r
    FROM rag.chunks, to_tsquery('simple', %(tsq)s) AS query
    WHERE {where} AND content_tsv @@ query
    ORDER BY ts_rank_cd(content_tsv, query) DESC LIMIT %(pool)s
)
SELECT c.document_id, c.page, c.chunk_index, c.content, 1 - (c.embedding <=> %(q)s) AS cosine,
       fts.id IS NOT NULL AS matched,
       coalesce(1.0 / (%(rrf)s + vec.r), 0) + coalesce(%(wf)s / (%(rrf)s + fts.r), 0) AS score
FROM rag.chunks c LEFT JOIN vec ON vec.id = c.id LEFT JOIN fts ON fts.id = c.id
WHERE vec.id IS NOT NULL OR fts.id IS NOT NULL
ORDER BY score DESC LIMIT %(k)s
"""


def search_hybrid(
    pool: ConnectionPool,
    owner_id: str,
    query_embedding: np.ndarray,
    query_text: str,
    top_k: int,
    document_ids: list[UUID] | None = None,
    content_contains: list[str] | None = None,
    *,
    max_df: float = 0.01,
    text_weight: float = 2.0,
    pool_size: int = 30,
) -> list[Hit]:
    """Vector search plus Swedish full-text search, fused with Reciprocal Rank Fusion.

    The text side only uses words found in at most `max_df` of the owner's chunks (case numbers, names, section
    numbers), because common words ("kommunstyrelsens", "sammanträde") would drown them. Without such a word it
    falls back to plain vector search. Hit.score is the chunk's cosine; the order is the fused rank."""
    df, total = _stats(pool, owner_id)
    with pool.connection() as conn:
        stems = [r[0] for r in conn.execute(
            "SELECT unnest(tsvector_to_array(to_tsvector('swedish', %s)))", (query_text,)).fetchall()]
    rare = [w for w in stems if 0 < df.get(w, 0) <= max_df * total]
    if not rare:
        return search(pool, owner_id, query_embedding, top_k, document_ids, content_contains)

    where, params = _filters(owner_id, document_ids, content_contains)
    params |= {
        "q": query_embedding, "k": top_k, "pool": pool_size, "rrf": 60, "wf": text_weight,
        "tsq": " | ".join("'" + w.replace("'", "''") + "'" for w in rare),
    }
    with pool.connection() as conn:
        rows = conn.execute(HYBRID_SQL.format(where=where), params).fetchall()
    return [Hit(r[0], r[1], r[2], r[3], r[4], matched=r[5]) for r in rows]


def neighbours(pool: ConnectionPool, owner_id: str, hits: list[Hit], reach: int) -> dict[tuple[UUID, int, int], str]:
    """The chunks up to `reach` steps before and after each hit, on the same page: {(document, page, index): text}."""
    wanted = [(h.document_id, h.page, h.chunk_index + step) for h in hits for step in range(-reach, reach + 1) if step]
    if not wanted:
        return {}
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT c.document_id, c.page, c.chunk_index, c.content FROM rag.chunks c "
            "JOIN (SELECT unnest(%(d)s::uuid[]) AS d, unnest(%(p)s::int[]) AS p, unnest(%(i)s::int[]) AS i) k "
            "ON c.document_id = k.d AND c.page = k.p AND c.chunk_index = k.i WHERE c.owner_id = %(owner)s",
            {"d": [w[0] for w in wanted], "p": [w[1] for w in wanted], "i": [w[2] for w in wanted], "owner": owner_id},
        ).fetchall()
    return {(r[0], r[1], r[2]): r[3] for r in rows}


def delete_document(pool: ConnectionPool, owner_id: str, document_id: UUID) -> int:
    with pool.connection() as conn:
        cur = conn.execute(
            "DELETE FROM rag.chunks WHERE owner_id = %s AND document_id = %s", (owner_id, document_id)
        )
        deleted = cur.rowcount
    _word_stats.pop(owner_id, None)
    return deleted
