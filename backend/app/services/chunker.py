"""Recursive character splitter with overlap and per-chunk page metadata.

Tries to cut on paragraph breaks first, then lines, sentences, words and only
as a last resort mid-word, so chunks usually end at natural boundaries.
"""
from __future__ import annotations

from dataclasses import dataclass

from .extractor import ExtractedPage

SEPARATORS = ["\n\n", "\n", ". ", " ", ""]
MIN_CHUNK_CHARS = 20


@dataclass
class Chunk:
    index: int          # running number across the whole document
    page: int | None
    text: str


def _merge(pieces: list[str], sep: str, size: int, overlap: int) -> list[str]:
    """Greedily pack pieces into chunks <= size, carrying `overlap` chars into the next chunk."""
    out: list[str] = []
    cur: list[str] = []

    def joined_len(items: list[str]) -> int:
        return len(sep.join(items)) if items else 0

    for piece in pieces:
        if cur and joined_len(cur + [piece]) > size:
            out.append(sep.join(cur))
            # Drop pieces from the front until the carried-over tail fits the overlap budget
            # and there is room for the new piece.
            while cur and (joined_len(cur) > overlap or joined_len(cur + [piece]) > size):
                cur.pop(0)
        cur.append(piece)
    if cur:
        out.append(sep.join(cur))
    return out


def split_text(text: str, size: int = 800, overlap: int = 150, seps: list[str] | None = None) -> list[str]:
    if overlap >= size:
        raise ValueError("overlap must be smaller than chunk size")
    seps = SEPARATORS if seps is None else seps
    if len(text) <= size:
        return [text]

    sep = ""
    rest: list[str] = []
    for i, s in enumerate(seps):
        if s == "" or s in text:
            sep, rest = s, seps[i + 1:]
            break

    parts = text.split(sep) if sep else list(text)
    chunks: list[str] = []
    good: list[str] = []
    for part in parts:
        if len(part) <= size:
            good.append(part)
            continue
        if good:
            chunks.extend(_merge(good, sep, size, overlap))
            good = []
        chunks.extend(split_text(part, size, overlap, rest) if rest else [part[:size]])
    if good:
        chunks.extend(_merge(good, sep, size, overlap))
    return chunks


def chunk_pages(pages: list[ExtractedPage], size: int, overlap: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page in pages:
        for piece in split_text(page.text, size, overlap):
            piece = piece.strip()
            if len(piece) >= MIN_CHUNK_CHARS:
                chunks.append(Chunk(index=len(chunks), page=page.page, text=piece))
    return chunks
