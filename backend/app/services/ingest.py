"""Upload -> extract -> chunk -> embed -> store. Runs in a background task."""
from __future__ import annotations

import logging
from pathlib import Path

from ..container import Container
from .chunker import chunk_pages
from .embedder import EmbeddingError
from .extractor import ExtractionError, extract_text

log = logging.getLogger("rag.ingest")


def ingest_document(container: Container, *, doc_id: str, owner_id: str, filename: str,
                    ext: str, raw_path: Path) -> None:
    s = container.settings
    try:
        content = raw_path.read_bytes()
        pages, page_count = extract_text(content, ext)
        chunks = chunk_pages(pages, s.chunk_size, s.chunk_overlap)
        if not chunks:
            raise ExtractionError("No readable text found in this file.")
        if len(chunks) > s.max_chunks_per_doc:
            raise ExtractionError(
                f"This document is too large to index ({len(chunks)} passages, limit {s.max_chunks_per_doc})."
            )
        embeddings = container.embedder.embed_texts([c.text for c in chunks])
        container.store.add_chunks(
            doc_id=doc_id, owner_id=owner_id, filename=filename, chunks=chunks, embeddings=embeddings
        )
        container.db.set_ready(doc_id, page_count, len(chunks))
        log.info("Indexed document %s: %d chunks", doc_id, len(chunks))  # ids/counts only - never text
    except (ExtractionError, EmbeddingError) as exc:
        container.store.delete_document(doc_id)
        container.db.set_failed(doc_id, str(exc))
        log.info("Document %s failed: %s", doc_id, exc)
    except Exception:  # noqa: BLE001
        container.store.delete_document(doc_id)
        container.db.set_failed(doc_id, "Unexpected error while processing this file.")
        log.exception("Unexpected failure while indexing document %s", doc_id)
    finally:
        # The raw upload is not needed once indexed; keeping less sensitive data at rest is safer.
        try:
            raw_path.unlink(missing_ok=True)
        except OSError:
            pass
