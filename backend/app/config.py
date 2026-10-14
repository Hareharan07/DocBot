"""Central configuration. Secrets come only from environment variables / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    groq_rewrite_model: str = "openai/gpt-oss-20b"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    data_dir: Path = BASE_DIR / "data"
    chunk_size: int = 800
    chunk_overlap: int = 150
    top_k: int = 5
    min_similarity: float = 0.15
    max_upload_mb: int = 10
    max_chunks_per_doc: int = 3000
    max_history_turns: int = 6
    chat_rate_per_min: int = 30
    upload_rate_per_min: int = 10
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def llm_configured(self) -> bool:
        return bool(self.groq_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    origins = tuple(
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if o.strip()
    )
    return Settings(
        groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
        groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
        groq_rewrite_model=os.getenv("GROQ_REWRITE_MODEL", "openai/gpt-oss-20b"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        data_dir=Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))),
        chunk_size=_int("CHUNK_SIZE", 800),
        chunk_overlap=_int("CHUNK_OVERLAP", 150),
        top_k=_int("TOP_K", 5),
        min_similarity=_float("MIN_SIMILARITY", 0.15),
        max_upload_mb=_int("MAX_UPLOAD_MB", 10),
        max_chunks_per_doc=_int("MAX_CHUNKS_PER_DOC", 3000),
        chat_rate_per_min=_int("CHAT_RATE_PER_MIN", 30),
        upload_rate_per_min=_int("UPLOAD_RATE_PER_MIN", 10),
        cors_origins=origins,
    )
