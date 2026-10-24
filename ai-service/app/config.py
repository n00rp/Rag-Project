from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://app:change-me-locally@localhost:5432/docassistant"
    internal_api_key: str = ""

    embedding_backend: Literal["fake", "sentence-transformers"] = "sentence-transformers"
    embedding_model: str = "intfloat/multilingual-e5-base"
    embedding_dim: int = 768  # must match the model; a change needs RESET_VECTORS_ON_DIM_CHANGE and a re-index (db.init_schema)
    reset_vectors_on_dim_change: bool = False

    llm_backend: Literal["fake", "ollama"] = "fake"
    llm_model: str = ""
    ollama_base_url: str = "http://localhost:11434"
    llm_timeout_seconds: float = 120.0

    # Drop running headers/footers before chunking. Switchable so phase 3 can measure its effect.
    strip_page_boilerplate: bool = True
    # Prefix every chunk with the document's first lines (date, body). Measured in eval/README.md.
    doc_header: bool = True
    # Chunks split at Kap./§ headings and carry the heading (needed for agreements; measured in eval/README.md).
    section_labels: bool = True
    # Questions with a case number or "§ N" also get a keyword search (hybrid), and a date like 2025-04-09 limits the
    # search to that meeting. Measured in eval/README.md (experiment "hybrid router").
    hybrid_identifiers: bool = True
    hybrid_max_df: float = 0.01  # keyword side only uses words found in at most this share of the chunks
    hybrid_text_weight: float = 2.0
    # Cross-encoder that reorders the best `rerank_pool` hits; empty = off (experiment, eval/README.md).
    rerank_model: str = ""
    rerank_pool: int = 30
    # Let the LLM rewrite everyday wording into the texts' terms before searching (app/rewrite.py, eval/README.md).
    rewrite_query: bool = False
    # A source named in the question ("enligt LAS", "semesterlagen") gets its own hits in the pool (app/sources.py).
    name_sources: bool = False
    hybrid_all: bool = False  # keyword search for every question, not only those with a number (experiment, eval/README.md)
    filter_by_date: bool = True
    # Give the model the chunks next to each hit (same page) as well; sources shown to the user stay the same.
    context_neighbors: int = 0
    # The model first says how well the excerpts support an answer (fullt/delvis/inget). Off until measured.
    structured_answer: bool = False
    # Overview questions ("sammanfatta", "hur många", "lista alla") get this many excerpts instead of top_k.
    broad_top_k: int = 12
    chunk_size: int = 900
    chunk_overlap: int = 150
    top_k: int = 5
    # Cosine floor for the best retrieved chunk (below it: refuse), tuned for multilingual-e5-small on the eval set (eval/README.md):
    # 0.83 refuses all unanswerable questions without costing correctness, 0.85 already loses answers.
    # The scores are model-specific; re-tune when the embedding model changes. 0 disables the refusal.
    min_score: float = 0.82  # e5-base; 0.83 was tuned for e5-small (eval/README.md)
    max_upload_bytes: int = 25 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
