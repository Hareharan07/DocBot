"""Text -> vector. Runs locally with sentence-transformers, so document text never leaves the machine."""
from __future__ import annotations

import logging
import threading
from typing import Protocol

log = logging.getLogger("rag.embedder")


class EmbeddingError(Exception):
    """Message is safe to show to the user."""


class Embedder(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        from sentence_transformers import SentenceTransformer

                        log.info("Loading embedding model %s", self.model_name)
                        self._model = SentenceTransformer(self.model_name)
                    except Exception as exc:  # noqa: BLE001
                        raise EmbeddingError(
                            "The embedding model could not be loaded. Check your internet connection "
                            "for the first run (the model downloads once), then try again."
                        ) from exc
        return self._model

    def warm_up(self) -> None:
        try:
            self._load()
        except EmbeddingError:
            log.warning("Embedding model warm-up failed; will retry on first use")

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        try:
            # normalize_embeddings=True -> unit vectors, so cosine similarity = dot product
            vectors = model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
        except Exception as exc:  # noqa: BLE001
            raise EmbeddingError("Failed to compute embeddings for this document.") from exc
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]
