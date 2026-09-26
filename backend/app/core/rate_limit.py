import time
from typing import Dict, Tuple
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from app.core.config import settings
from app.core.logging import logger

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    In-memory sliding window rate limiter middleware.
    Protects against brute force and Denial of Service (DoS) attacks.
    """
    request_records: Dict[str, list[float]] = {}

    def __init__(self, app, max_requests: int = 120, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.last_cleanup = time.time()

    @classmethod
    def reset(cls):
        """Reset rate limiter state, useful for testing."""
        cls.request_records.clear()

    def _cleanup_old_records(self, now: float):
        """Periodically purge entries older than window_seconds to prevent memory growth."""
        if now - self.last_cleanup > 300: # Every 5 minutes
            cutoff = now - self.window_seconds
            keys_to_delete = []
            for ip, timestamps in self.request_records.items():
                active = [t for t in timestamps if t > cutoff]
                if active:
                    self.request_records[ip] = active
                else:
                    keys_to_delete.append(ip)
            for k in keys_to_delete:
                del self.request_records[k]
            self.last_cleanup = now

    async def dispatch(self, request: Request, call_next):
        # Allow internal health checks to bypass rate limit
        if request.url.path.startswith("/api/v1/health") or request.url.path == "/":
            return await call_next(request)

        now = time.time()
        self._cleanup_old_records(now)

        # Extract client IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        cutoff = now - self.window_seconds
        timestamps = self.request_records.get(client_ip, [])
        valid_timestamps = [t for t in timestamps if t > cutoff]

        # Stricter rate limiting on auth endpoints (e.g., login: 20 per minute)
        max_allowed = 20 if request.url.path.endswith("/login") else self.max_requests

        if len(valid_timestamps) >= max_allowed:
            retry_after = int(self.window_seconds - (now - valid_timestamps[0]))
            retry_after = max(1, retry_after)
            logger.warning(
                f"Rate limit exceeded for IP: {client_ip} on {request.url.path}",
                extra={"extra_data": {"client_ip": client_ip, "path": request.url.path, "count": len(valid_timestamps)}}
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": f"Rate limit exceeded. Try again in {retry_after} seconds.",
                    "retry_after": retry_after
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(max_allowed),
                    "X-RateLimit-Remaining": "0"
                }
            )

        valid_timestamps.append(now)
        self.request_records[client_ip] = valid_timestamps

        response = await call_next(request)
        remaining = max(0, max_allowed - len(valid_timestamps))
        response.headers["X-RateLimit-Limit"] = str(max_allowed)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
