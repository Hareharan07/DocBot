"""Upload validation + text extraction for PDF, DOCX and TXT."""
from __future__ import annotations

import io
import os
import re
import zipfile
from dataclasses import dataclass

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_DOCX_UNCOMPRESSED = 60 * 1024 * 1024  # guards against zip bombs
MIN_TEXT_CHARS = 20


class ExtractionError(Exception):
    """Message is safe to show to the user."""


@dataclass
class ExtractedPage:
    page: int | None  # None for formats without reliable pages (DOCX, TXT)
    text: str


def safe_display_name(filename: str | None) -> str:
    """Strip any path, control characters and oversized names. Display only - never used as a path."""
    name = (filename or "document").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip().strip(".")
    return (name or "document")[:120]


def get_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def validate_upload(filename: str, content: bytes) -> str:
    """Return the validated extension or raise ExtractionError."""
    ext = get_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ExtractionError("Unsupported file type. Upload a PDF, DOCX or TXT file.")
    if not content:
        raise ExtractionError("This file is empty.")
    # Don't trust the extension alone: check the file's real signature.
    if ext == ".pdf" and not content.lstrip()[:5].startswith(b"%PDF"):
        raise ExtractionError("This file is not a valid PDF.")
    if ext == ".docx" and not content.startswith(b"PK\x03\x04"):
        raise ExtractionError("This file is not a valid DOCX.")
    if ext == ".txt" and b"\x00" in content[:8192]:
        raise ExtractionError("This file looks like binary data, not plain text.")
    return ext


def clean_text(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_pdf(content: bytes) -> list[ExtractedPage]:
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            try:
                ok = reader.decrypt("")
            except Exception:
                ok = 0
            if not ok:
                raise ExtractionError("This PDF is password-protected.")
        pages = []
        for i, page in enumerate(reader.pages, start=1):
            try:
                text = clean_text(page.extract_text() or "")
            except Exception:
                text = ""
            if text:
                pages.append(ExtractedPage(page=i, text=text))
        total_pages = len(reader.pages)
    except ExtractionError:
        raise
    except (PyPdfError, Exception) as exc:  # noqa: BLE001 - corrupt PDFs raise many types
        raise ExtractionError("This PDF is corrupted or could not be read.") from exc

    if sum(len(p.text) for p in pages) < MIN_TEXT_CHARS:
        raise ExtractionError(
            f"No readable text found in this PDF ({total_pages} page(s)). "
            "It may be a scan or image-only PDF, which isn't supported."
        )
    return pages


def _extract_docx(content: bytes) -> list[ExtractedPage]:
    import docx

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            if sum(i.file_size for i in zf.infolist()) > MAX_DOCX_UNCOMPRESSED:
                raise ExtractionError("This DOCX expands to an unreasonable size.")
        document = docx.Document(io.BytesIO(content))
        parts = [p.text for p in document.paragraphs if p.text.strip()]
        for table in document.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))
        text = clean_text("\n\n".join(parts))
    except ExtractionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError("This DOCX is corrupted or could not be read.") from exc

    if len(text) < MIN_TEXT_CHARS:
        raise ExtractionError("No readable text found in this document.")
    return [ExtractedPage(page=None, text=text)]


def _extract_txt(content: bytes) -> list[ExtractedPage]:
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            text = clean_text(content.decode(encoding))
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        raise ExtractionError("Could not decode this text file.")
    if len(text) < MIN_TEXT_CHARS:
        raise ExtractionError("No readable text found in this file.")
    return [ExtractedPage(page=None, text=text)]


def extract_text(content: bytes, ext: str) -> tuple[list[ExtractedPage], int | None]:
    """Return (pages, page_count). page_count is None when the format has no pages."""
    if ext == ".pdf":
        pages = _extract_pdf(content)
        return pages, max(p.page for p in pages if p.page)  # type: ignore[arg-type]
    if ext == ".docx":
        return _extract_docx(content), None
    if ext == ".txt":
        return _extract_txt(content), None
    raise ExtractionError("Unsupported file type.")
