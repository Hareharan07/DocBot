from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import Settings, get_settings
from .container import Container
from .db import Database
from .errors import install_error_handlers
from .routes import chat, documents, health
from .security import RateLimiter
from .services.embedder import Embedder, SentenceTransformerEmbedder
from .services.llm import GroqLLM, LLMClient
from .services.vector_store import VectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("rag")

FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def create_app(settings: Settings | None = None, embedder: Embedder | None = None,
               llm: LLMClient | None = None, use_default_llm: bool = True) -> FastAPI:
    settings = settings or get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    if llm is None and use_default_llm and settings.llm_configured:
        llm = GroqLLM(settings.groq_api_key, settings.groq_model, settings.groq_rewrite_model)
    embedder = embedder or SentenceTransformerEmbedder(settings.embedding_model)

    container = Container(
        settings=settings, db=Database(settings.db_path), store=VectorStore(settings.chroma_dir),
        embedder=embedder, llm=llm, limiter=RateLimiter(),
    )
    interrupted = container.db.fail_interrupted()
    if interrupted:
        log.warning("Marked %d interrupted document(s) as failed", interrupted)
    if llm is None:
        log.warning("GROQ_API_KEY is not set - chat is disabled until you add it to backend/.env")

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # Load the embedding model in the background so the first upload isn't slow.
        warm = getattr(embedder, "warm_up", None)
        if callable(warm):
            threading.Thread(target=warm, daemon=True).start()
        yield

    app = FastAPI(title="DocBot RAG API", version="1.0.0", lifespan=lifespan)
    app.state.container = container
    install_error_handlers(app)

    app.add_middleware(
        CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-Owner-Id"],
    )

    @app.middleware("http")
    async def reject_oversized_uploads(request: Request, call_next):
        # Cheap early rejection using Content-Length before the body is spooled.
        if request.method == "POST" and request.url.path == "/api/documents":
            length = request.headers.get("content-length")
            if length and length.isdigit() and int(length) > settings.max_upload_bytes + 1_048_576:
                return JSONResponse(
                    {"error": {"code": "file_too_large",
                               "message": f"File is larger than {settings.max_upload_mb} MB."}},
                    status_code=413,
                )
        return await call_next(request)

    app.include_router(health.router, prefix="/api")
    app.include_router(documents.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")

    # Optional: serve the built frontend from the same server (npm run build first).
    if FRONTEND_DIST.exists():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    return app
