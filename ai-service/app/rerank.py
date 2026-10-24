"""Cross-encoder reranking: reads question and chunk together, so it can tell the law a question names from a long
commentary that merely discusses it. Slower than the vector search, so it only reorders a shortlist."""
from dataclasses import replace
from functools import lru_cache

from app.db import Hit


@lru_cache(maxsize=2)
def _model(name: str):
    from sentence_transformers import CrossEncoder  # heavy import, keep lazy

    return CrossEncoder(name, max_length=512)


def rerank(model_name: str, question: str, hits: list[Hit], k: int) -> list[Hit]:
    """The k best hits by cross-encoder score; the score replaces the cosine score only in the order, `score` stays."""
    if len(hits) <= 1:
        return hits[:k]
    scores = _model(model_name).predict([(question, h.content) for h in hits], batch_size=16)
    order = sorted(range(len(hits)), key=lambda i: scores[i], reverse=True)
    return [replace(hits[i]) for i in order[:k]]
