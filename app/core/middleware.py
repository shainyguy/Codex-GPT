import time
from collections import defaultdict, deque

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit: int = 60, period: int = 60):
        super().__init__(app)
        self.limit = limit
        self.period = period
        self.requests = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        key = request.client.host if request.client else 'unknown'
        now = time.time()
        bucket = self.requests[key]
        while bucket and now - bucket[0] > self.period:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return JSONResponse({'detail': 'Rate limit exceeded'}, status_code=429)
        bucket.append(now)
        return await call_next(request)
