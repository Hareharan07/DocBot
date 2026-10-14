"""Owner identification and rate limiting.

IMPORTANT: this is *isolation*, not authentication. Each browser generates a random
unguessable owner id; every document and query is scoped to it. Anyone who has the id
can access those documents, so for a public/multi-user deployment add real login
(e.g. JWT/OAuth) and derive owner_id from the verified user instead of a header.
"""
from __future__ import annotations

import re
import time
from collections import defaultdict, deque

from fastapi import Header, Request

from .errors import ApiError

OWNER_RE = re.compile(r"^[A-Za-z0-9-]{16,64}$")


def get_owner_id(x_owner_id: str | None = Header(default=None)) -> str:
    if not x_owner_id or not OWNER_RE.match(x_owner_id):
        raise ApiError(401, "missing_owner", "Missing or invalid X-Owner-Id header.")
    return x_owner_id


class RateLimiter:
    """Tiny in-memory sliding window. Use Redis (or a gateway) if you run several workers."""

    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def check(self, owner_id: str, bucket: str, limit: int, window: float = 60.0) -> None:
        now = time.monotonic()
        q = self._hits[(owner_id, bucket)]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            raise ApiError(429, "rate_limited", "Too many requests. Please wait a moment and try again.")
        q.append(now)


def get_container(request: Request):
    return request.app.state.container
