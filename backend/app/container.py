"""Holds the long-lived services. Tests build their own Container with fakes."""
from __future__ import annotations

from dataclasses import dataclass

from .config import Settings
from .db import Database
from .security import RateLimiter
from .services.embedder import Embedder
from .services.llm import LLMClient
from .services.vector_store import VectorStore


@dataclass
class Container:
    settings: Settings
    db: Database
    store: VectorStore
    embedder: Embedder
    llm: LLMClient | None  # None => GROQ_API_KEY missing
    limiter: RateLimiter
