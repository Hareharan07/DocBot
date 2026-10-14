"""SQLite metadata store (document list, status, hash for duplicate detection)."""
from __future__ import annotations

import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id          TEXT PRIMARY KEY,
    owner_id    TEXT NOT NULL,
    filename    TEXT NOT NULL,
    file_type   TEXT NOT NULL,
    size_bytes  INTEGER NOT NULL,
    sha256      TEXT NOT NULL,
    status      TEXT NOT NULL,          -- processing | ready | failed
    error       TEXT,
    page_count  INTEGER,
    chunk_count INTEGER,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_owner ON documents(owner_id, created_at);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(owner_id, sha256);
"""


@dataclass
class Document:
    id: str
    owner_id: str
    filename: str
    file_type: str
    size_bytes: int
    sha256: str
    status: str
    error: str | None
    page_count: int | None
    chunk_count: int | None
    created_at: float


class Database:
    """A fresh connection per call keeps this safe across FastAPI's worker threads."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _row(row: sqlite3.Row | None) -> Document | None:
        return Document(**dict(row)) if row else None

    def create_document(self, *, owner_id: str, filename: str, file_type: str,
                        size_bytes: int, sha256: str) -> Document:
        doc_id = uuid.uuid4().hex
        with self._conn() as c:
            c.execute(
                "INSERT INTO documents (id, owner_id, filename, file_type, size_bytes, sha256,"
                " status, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (doc_id, owner_id, filename, file_type, size_bytes, sha256, "processing", time.time()),
            )
        return self.get_document(doc_id, owner_id)  # type: ignore[return-value]

    def get_document(self, doc_id: str, owner_id: str) -> Document | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM documents WHERE id=? AND owner_id=?", (doc_id, owner_id)
            ).fetchone()
        return self._row(row)

    def list_documents(self, owner_id: str) -> list[Document]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM documents WHERE owner_id=? ORDER BY created_at DESC", (owner_id,)
            ).fetchall()
        return [Document(**dict(r)) for r in rows]

    def find_by_hash(self, owner_id: str, sha256: str) -> Document | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM documents WHERE owner_id=? AND sha256=? ORDER BY created_at DESC LIMIT 1",
                (owner_id, sha256),
            ).fetchone()
        return self._row(row)

    def set_ready(self, doc_id: str, page_count: int | None, chunk_count: int) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE documents SET status='ready', error=NULL, page_count=?, chunk_count=? WHERE id=?",
                (page_count, chunk_count, doc_id),
            )

    def set_failed(self, doc_id: str, error: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE documents SET status='failed', error=? WHERE id=?", (error, doc_id))

    def delete_document(self, doc_id: str, owner_id: str) -> bool:
        with self._conn() as c:
            cur = c.execute("DELETE FROM documents WHERE id=? AND owner_id=?", (doc_id, owner_id))
            return cur.rowcount > 0

    def fail_interrupted(self) -> int:
        """Documents left in 'processing' by a crash/restart can never finish; mark them failed."""
        with self._conn() as c:
            cur = c.execute(
                "UPDATE documents SET status='failed', error=? WHERE status='processing'",
                ("Processing was interrupted by a server restart. Delete this file and upload it again.",),
            )
            return cur.rowcount
