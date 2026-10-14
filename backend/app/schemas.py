from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .db import Document


class DocumentOut(BaseModel):
    id: str
    filename: str
    file_type: str
    size_bytes: int
    status: Literal["processing", "ready", "failed"]
    error: str | None = None
    page_count: int | None = None
    chunk_count: int | None = None
    created_at: float

    @classmethod
    def from_doc(cls, d: Document) -> "DocumentOut":
        return cls(**{k: getattr(d, k) for k in cls.model_fields})


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    doc_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    question: str = Field(min_length=1, max_length=1000)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=20)

    @field_validator("question")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Question cannot be empty")
        return v


class SourceOut(BaseModel):
    label: str
    filename: str
    page: int | None
    chunk_index: int
    snippet: str
    similarity: float


class ChatResponse(BaseModel):
    answer: str
    found: bool          # False => the document doesn't contain the answer
    grounded: bool       # False => answered but no citation could be verified
    sources: list[SourceOut]
    standalone_question: str
