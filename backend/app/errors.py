"""One error shape for the whole API: {"error": {"code": ..., "message": ...}}."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, extra: dict | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra or {}


def _body(code: str, message: str, extra: dict | None = None) -> dict:
    err = {"code": code, "message": message}
    if extra:
        err.update(extra)
    return {"error": err}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return JSONResponse(_body(exc.code, exc.message, exc.extra), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", []) if p not in ("body", "header"))
        msg = first.get("msg", "Invalid request")
        return JSONResponse(_body("invalid_request", f"{loc}: {msg}" if loc else msg), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        return JSONResponse(_body("http_error", str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        # Never leak internals (or document text) to the client.
        return JSONResponse(_body("internal_error", "Something went wrong on the server."), status_code=500)
