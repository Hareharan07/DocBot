"""Test doubles. The real embedding model and Groq are replaced so tests run offline.

FakeEmbedder is a hashed bag-of-words: it measures *word overlap*, not true meaning.
So these tests prove the pipeline logic (filtering, thresholds, citations, persistence);
semantic matching with different wording must be checked manually with the real model.
"""
from __future__ import annotations

import hashlib
import io
import math
import re
import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

STOP = {"the", "a", "an", "is", "of", "to", "and", "in", "on", "for", "what", "how", "does", "do", "are", "it", "this", "that", "with", "by", "be", "as", "at", "or"}
DIM = 512


class FakeEmbedder:
    def _vec(self, text: str) -> list[float]:
        v = [0.0] * DIM
        for tok in re.findall(r"[a-z0-9]+", text.lower()):
            if tok in STOP:
                continue
            v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % DIM] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed_texts(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


class FakeLLM:
    """Cites every passage it is given, like a well-behaved model. Records calls."""

    def __init__(self):
        self.answer_calls = 0
        self.last_passages = []
        self.rewrite_calls = 0
        self.mode = "cite_all"  # cite_all | invalid_cite | no_cite | insufficient

    def rewrite_question(self, history, question):
        self.rewrite_calls += 1
        return question + " " + history[-1]["content"][:40]

    def answer(self, question, passages, history):
        self.answer_calls += 1
        self.last_passages = passages
        if self.mode == "insufficient":
            return "INSUFFICIENT_INFORMATION"
        if self.mode == "no_cite":
            return "Something unverifiable."
        if self.mode == "invalid_cite":
            return "Claim [S1] and invented [S99]."
        labels = "".join(f"[S{i}]" for i in range(1, len(passages) + 1))
        return f"Answer based on the document {labels}"


def make_settings(tmp_path, **kw) -> Settings:
    base = dict(data_dir=tmp_path, groq_api_key="gsk_test_secret_value_123", min_similarity=0.25,
                chat_rate_per_min=1000, upload_rate_per_min=1000)
    base.update(kw)
    return Settings(**base)


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
def settings(tmp_path):
    return make_settings(tmp_path)


@pytest.fixture
def client(settings, fake_llm):
    app = create_app(settings, embedder=FakeEmbedder(), llm=fake_llm)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def owner():
    return str(uuid.uuid4())


@pytest.fixture
def h(owner):
    return {"X-Owner-Id": owner}


def make_pdf(pages: list[str]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for text in pages:
        y = 800
        for line in text.split("\n"):
            c.drawString(60, y, line)
            y -= 16
        c.showPage()
    c.save()
    return buf.getvalue()


def make_docx(paragraphs: list[str]) -> bytes:
    import docx

    d = docx.Document()
    for p in paragraphs:
        d.add_paragraph(p)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def upload(client, headers, name, content, mime="application/octet-stream"):
    return client.post("/api/documents", files={"file": (name, content, mime)}, headers=headers)


def ask(client, headers, doc_id, question, history=None):
    return client.post("/api/chat", json={"doc_id": doc_id, "question": question, "history": history or []},
                       headers=headers)
