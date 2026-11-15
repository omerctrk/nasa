"""Sentence-Transformers implementation for multilingual E5 retrieval."""

from __future__ import annotations

from threading import RLock

from sentence_transformers import SentenceTransformer

from app.embeddings.base import EmbeddingProvider


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Load multilingual-e5-base once and produce normalized retrieval vectors."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model: SentenceTransformer | None = None
        self._dimension: int | None = None
        self._load_lock = RLock()

    @property
    def dimension(self) -> int:
        self.load()
        assert self._dimension is not None
        return self._dimension

    def load(self) -> None:
        """Load the local/cache-backed model at most once per application process."""
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is None:
                model = SentenceTransformer(self._model_name)
                dimension = model.get_sentence_embedding_dimension()
                if dimension is None or dimension <= 0:
                    raise ValueError("Embedding model did not report a valid vector dimension.")
                self._model = model
                self._dimension = dimension

    @staticmethod
    def prepare_passage(text: str) -> str:
        """Apply the prefix required by E5 for stored retrieval passages."""
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("A Knowledge Card passage must not be blank.")
        return f"passage: {cleaned}"

    @staticmethod
    def prepare_query(query: str) -> str:
        """Apply the prefix required by E5 for a retrieval query."""
        cleaned = query.strip()
        if not cleaned:
            raise ValueError("A retrieval query must not be blank.")
        return f"query: {cleaned}"

    def _encode(self, texts: list[str]) -> list[list[float]]:
        self.load()
        assert self._model is not None
        vectors = self._model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return [[float(value) for value in vector] for vector in vectors.tolist()]

    def embed_passages(self, passages: list[str]) -> list[list[float]]:
        """Embed Knowledge Card text as E5 passages."""
        if not passages:
            return []
        return self._encode([self.prepare_passage(passage) for passage in passages])

    def embed_query(self, query: str) -> list[float]:
        """Embed one user query as an E5 query."""
        return self._encode([self.prepare_query(query)])[0]
