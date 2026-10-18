"""CSRF guard and simple rate limiting.

CSRF: state-changing requests must carry `X-CityPulse-Client`. Browsers cannot attach custom headers to
cross-site form posts, and CORS only allows our web origin, so a forged cross-site request is rejected.
"""

import os
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in UNSAFE and request.url.path.startswith("/api/"):
            if request.headers.get("x-citypulse-client") != "web":
                return JSONResponse({"error": "csrf", "message": "Missing client header."}, status_code=403)
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory sliding window for writes: fine for a single-process hackathon deployment."""

    def __init__(self, app, writes_per_minute: int | None = None):
        super().__init__(app)
        self.limit = writes_per_minute or int(os.environ.get("RATE_LIMIT_WRITES_PER_MINUTE", "40"))
        self.hits: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if request.method in UNSAFE:
            key = request.client.host if request.client else "unknown"
            now = time.monotonic()
            q = self.hits[key]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self.limit:
                return JSONResponse({"error": "rate_limited", "message": "Too many requests, slow down."},
                                    status_code=429)
            q.append(now)
        return await call_next(request)
