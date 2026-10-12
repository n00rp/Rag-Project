import hashlib
import re
from typing import Protocol

import numpy as np

from app.config import Settings


class Embedder(Protocol):
    dim: int

    def embed_passages(self, texts: list[str]) -> np.ndarray: ...

    def embed_query(self, text: str) -> np.ndarray: ...


class FakeEmbedder:
    """Deterministic hashed bag-of-words. Similar word overlap => similar vectors.

    Only for tests and for running the stack without ML dependencies.
    """

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def _embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        for token in re.findall(r"\w+", text.lower()):
            digest = hashlib.md5(token.encode("utf-8")).digest()
            vec[int.from_bytes(digest[:4], "little") % self.dim] += 1.0
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._embed(t) for t in texts])

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed(text)


class SentenceTransformerEmbedder:
    """multilingual-e5 expects 'passage: ' / 'query: ' prefixes."""

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer  # heavy import, keep lazy

        self._model = SentenceTransformer(model_name)
        self.dim = self._model.get_sentence_embedding_dimension()

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(
            [f"passage: {t}" for t in texts], normalize_embeddings=True, batch_size=32
        )

    def embed_query(self, text: str) -> np.ndarray:
        return self._model.encode(f"query: {text}", normalize_embeddings=True)


def build_embedder(settings: Settings) -> Embedder:
    if settings.embedding_backend == "fake":
        return FakeEmbedder(settings.embedding_dim)
    embedder = SentenceTransformerEmbedder(settings.embedding_model)
    if embedder.dim != settings.embedding_dim:
        raise RuntimeError(
            f"Modellen ger {embedder.dim} dimensioner men EMBEDDING_DIM={settings.embedding_dim}"
        )
    return embedder
