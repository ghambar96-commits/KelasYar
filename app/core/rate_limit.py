"""Lightweight sliding-window rate limiter for the REST API.

Per-identity buckets (API key > bearer token > client IP) with a configurable
request count per time window.  Runs in-memory – for multi-instance
deployments swap the bucket store for Redis (see README roadmap).
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

EXEMPT_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json", "/admin"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max(1, max_requests)
        self.window = max(1, window_seconds)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        key = self._identity(request)

        async with self._lock:
            now = time.monotonic()
            bucket = self._hits[key]
            while bucket and bucket[0] <= now - self.window:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                retry_after = max(1, int(bucket[0] + self.window - now) + 1)
                return JSONResponse(
                    status_code=429,
                    content={"error": "rate_limited", "detail": "Too many requests."},
                    headers={"Retry-After": str(retry_after)},
                )
            bucket.append(now)
            if len(self._hits) > 10_000:  # rudimentary memory guard
                self._prune(now)

        return await call_next(request)

    @staticmethod
    def _identity(request: Request) -> str:
        api_key = request.headers.get("x-api-key")
        if api_key:
            return f"key:{hash(api_key)}"
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            return f"tok:{hash(auth[7:])}"
        client = request.client
        return f"ip:{client.host if client else 'anonymous'}"

    def _prune(self, now: float) -> None:
        stale = [k for k, v in self._hits.items() if not v or v[-1] <= now - self.window * 2]
        for k in stale:
            self._hits.pop(k, None)
