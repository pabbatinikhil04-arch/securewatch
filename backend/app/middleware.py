import time
from collections import defaultdict, deque
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds standard defensive HTTP headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        # Only meaningful over HTTPS deployments; harmless to send over HTTP.
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory sliding-window rate limiter, keyed by client IP + path.

    Not distributed (won't work across multiple server processes/instances) —
    fine for a single-instance dev/demo deployment. For production with
    multiple workers, replace with a Redis-backed limiter.
    """

    def __init__(self, app, limits: dict[str, tuple[int, int]] | None = None, default_limit=(100, 60)):
        super().__init__(app)
        # path_prefix -> (max_requests, window_seconds)
        self.limits = limits or {}
        self.default_limit = default_limit
        self.hits: dict[str, deque] = defaultdict(deque)

    def _limit_for(self, path: str):
        for prefix, limit in self.limits.items():
            if path.startswith(prefix):
                return limit
        return self.default_limit

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        key = f"{client_ip}:{path}"
        max_requests, window = self._limit_for(path)

        now = time.time()
        window_start = now - window
        bucket = self.hits[key]
        while bucket and bucket[0] < window_start:
            bucket.popleft()

        if len(bucket) >= max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down and try again shortly."},
            )

        bucket.append(now)
        return await call_next(request)
