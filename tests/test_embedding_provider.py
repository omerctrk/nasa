from __future__ import annotations

import numpy as np

from app.embeddings.sentence_transformer_provider import SentenceTransformerEmbeddingProvider


class FakeSentenceTransformer:
    instances = 0
    encoded_inputs: list[list[str]] = []
    encode_options: list[dict[str, object]] = []

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        type(self).instances += 1

    def get_sentence_embedding_dimension(self) -> int:
        return 3

    def encode(self, texts: list[str], **kwargs: object) -> np.ndarray:
        type(self).encoded_inputs.append(texts)
        type(self).encode_options.append(kwargs)
        return np.array([[0.1, 0.2, 0.3] for _ in texts])


def test_e5_provider_prefixes_normalizes_and_loads_once(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.embeddings.sentence_transformer_provider.SentenceTransformer",
        FakeSentenceTransformer,
    )
    provider = SentenceTransformerEmbeddingProvider("intfloat/multilingual-e5-base")

    passage_vectors = provider.embed_passages(["source card text"])
    query_vector = provider.embed_query("find respiratory information")

    assert provider.dimension == 3
    assert FakeSentenceTransformer.instances == 1
    assert FakeSentenceTransformer.encoded_inputs == [
        ["passage: source card text"],
        ["query: find respiratory information"],
    ]
    assert all(options["normalize_embeddings"] is True for options in FakeSentenceTransformer.encode_options)
    assert passage_vectors == [[0.1, 0.2, 0.3]]
    assert query_vector == [0.1, 0.2, 0.3]
