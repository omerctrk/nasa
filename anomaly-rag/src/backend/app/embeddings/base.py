"""Embedding provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Create normalized vectors for retrieval passages and queries."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the verified vector size after the provider is loaded."""

    @abstractmethod
    def load(self) -> None:
        """Load provider resources once for the process."""

    @abstractmethod
    def embed_passages(self, passages: list[str]) -> list[list[float]]:
        """Embed card passages with the model-specific retrieval prefix."""

    @abstractmethod
    def embed_query(self, query: str) -> list[float]:
        """Embed one user query with the model-specific retrieval prefix."""
