"""The answer pipeline: rewrite -> retrieve -> threshold -> generate -> verify citations."""
from __future__ import annotations

import logging
import re

from ..container import Container
from ..db import Document
from ..errors import ApiError
from .embedder import EmbeddingError
from .llm import LLMError
from .prompts import INSUFFICIENT_SENTINEL
from .vector_store import Passage

log = logging.getLogger("rag.chat")
CITATION = re.compile(r"\[S(\d+)\]")
BROAD_QUERY = re.compile(
    r"\b(summary|summarize|overview|gist|key\s+(dates?|names?|numbers?|points?|facts?)|"
    r"main\s+(conclusions?|decisions?|points?|ideas?)|important|takeaways?|"
    r"what\s+is\s+(this|the\s+document|it)|describe\s+(this|the\s+document))\b",
    re.IGNORECASE,
)


def _clean_history(history: list[dict], max_turns: int) -> list[dict]:
    cleaned = [
        {"role": m["role"], "content": m["content"].strip()[:1500]}
        for m in history
        if m.get("role") in ("user", "assistant") and str(m.get("content", "")).strip()
    ]
    return cleaned[-(max_turns * 2):]


def _insufficient(doc: Document, standalone: str) -> dict:
    return {
        "answer": f"The document \u201c{doc.filename}\u201d doesn't contain enough information to answer that.",
        "found": False,
        "grounded": True,
        "sources": [],
        "standalone_question": standalone,
    }


def _retrieval_k(question: str, default: int) -> int:
    """Use more passages for document-wide questions, without slowing normal queries."""
    return max(default, 12) if BROAD_QUERY.search(question) else default


def answer_question(container: Container, doc: Document, question: str, history: list[dict]) -> dict:
    s = container.settings
    history = _clean_history(history, s.max_history_turns)

    # 1) Make follow-ups searchable on their own ("what about the second one?").
    standalone = question
    if history:
        try:
            standalone = container.llm.rewrite_question(history, question)
        except LLMError:
            standalone = question  # rewriting is an optimisation; fall back to the raw question

    # 2) Retrieve from THIS document + owner only.
    try:
        query_vec = container.embedder.embed_query(standalone)
    except EmbeddingError as exc:
        raise ApiError(503, "embedding_unavailable", str(exc)) from exc
    found = container.store.query(
        embedding=query_vec, doc_id=doc.id, owner_id=doc.owner_id,
        k=_retrieval_k(standalone, s.top_k),
    )

    # 3) Guard rail #1: if nothing is similar enough, don't even call the LLM.
    passages: list[Passage] = [p for p in found if p.similarity >= s.min_similarity]
    if not passages:
        return _insufficient(doc, standalone)

    # 4) Generate.
    try:
        raw = container.llm.answer(question, passages, history)
    except LLMError as exc:
        raise ApiError(502, "llm_error", str(exc)) from exc

    # 5) Guard rail #2: the model itself may say the context isn't enough.
    if raw.strip().startswith(INSUFFICIENT_SENTINEL):
        return _insufficient(doc, standalone)

    # 6) Citations are built by the backend from real metadata; invented labels are dropped.
    valid = {i for i in range(1, len(passages) + 1)}
    cited: list[int] = []
    for m in CITATION.finditer(raw):
        n = int(m.group(1))
        if n in valid and n not in cited:
            cited.append(n)
    answer = CITATION.sub(lambda m: m.group(0) if int(m.group(1)) in valid else "", raw).strip()

    sources = [
        {
            "label": f"S{n}",
            "filename": passages[n - 1].filename,
            "page": passages[n - 1].page,
            "chunk_index": passages[n - 1].chunk_index,
            "snippet": passages[n - 1].text[:400],
            "similarity": passages[n - 1].similarity,
        }
        for n in cited
    ]
    return {
        "answer": answer,
        "found": True,
        "grounded": bool(sources),  # False => the model answered without any verifiable citation
        "sources": sources,
        "standalone_question": standalone,
    }
