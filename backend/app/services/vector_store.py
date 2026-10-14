"""ChromaDB wrapper. Persistent on disk; every query is filtered by document AND owner."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from .chunker import Chunk

COLLECTION = "document_chunks"
BATCH = 256


@dataclass
class Passage:
    doc_id: str
    filename: str
    page: int | None
    chunk_index: int
    text: str
    similarity: float


class VectorStore:
    def __init__(self, path: Path):
        Path(path).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(path), settings=ChromaSettings(anonymized_telemetry=False)
        )
        # We supply our own embeddings, so no embedding_function. Cosine distance.
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION, metadata={"hnsw:space": "cosine"}, embedding_function=None
        )

    def add_chunks(self, *, doc_id: str, owner_id: str, filename: str,
                   chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        for start in range(0, len(chunks), BATCH):
            batch = chunks[start:start + BATCH]
            self.collection.add(
                ids=[f"{doc_id}:{c.index}" for c in batch],
                embeddings=embeddings[start:start + BATCH],
                documents=[c.text for c in batch],
                metadatas=[
                    {
                        "doc_id": doc_id,
                        "owner_id": owner_id,
                        "filename": filename,
                        "page": c.page or 0,  # Chroma rejects None; 0 means "no page"
                        "chunk_index": c.index,
                    }
                    for c in batch
                ],
            )

    def query(self, *, embedding: list[float], doc_id: str, owner_id: str, k: int) -> list[Passage]:
        total = self.count(doc_id)
        if total == 0:
            return []
        res = self.collection.query(
            query_embeddings=[embedding],
            n_results=min(k, total),
            where={"$and": [{"doc_id": doc_id}, {"owner_id": owner_id}]},
            include=["documents", "metadatas", "distances"],
        )
        passages: list[Passage] = []
        for text, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            passages.append(
                Passage(
                    doc_id=meta["doc_id"],
                    filename=meta["filename"],
                    page=meta["page"] or None,
                    chunk_index=meta["chunk_index"],
                    text=text,
                    similarity=round(1.0 - float(dist), 4),  # cosine distance -> similarity
                )
            )
        return passages

    def count(self, doc_id: str) -> int:
        return len(self.collection.get(where={"doc_id": doc_id}, include=[])["ids"])

    def delete_document(self, doc_id: str) -> None:
        self.collection.delete(where={"doc_id": doc_id})
