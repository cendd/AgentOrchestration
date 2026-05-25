"""API middleware components."""

import time
import logging
from typing import Callable, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.common.auth import TokenManager

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Enhanced auth middleware with refresh token session rotation."""

    def __init__(self, app, token_manager: Optional[TokenManager] = None):
        super().__init__(app)
        self.token_manager = token_manager or TokenManager()
        # Protected routes (excluding auth endpoints)
        self._protected_prefixes = ["/api/v2"]
        self._excluded_paths = {"/api/v2/auth/token", "/api/v2/auth/refresh", "/health"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip auth for excluded paths
        if request.url.path in self._excluded_paths:
            return await call_next(request)

        # Check if route needs auth
        needs_auth = any(request.url.path.startswith(p) for p in self._protected_prefixes)

        if needs_auth:
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return Response(status_code=401, content='{"error":"Missing or invalid Authorization header"}',
                                media_type="application/json")

            token = auth_header[7:]

            # 1. Basic token validation
            if not self.token_manager.validate_token(token):
                return Response(status_code=401,
                                content='{"error":"Token is invalid, expired, or stale — please re-authenticate"}',
                                media_type="application/json")

            # 2. Session rotation check
            if not self.token_manager.check_session_rotation(token):
                return Response(status_code=401,
                                content='{"error":"Session has been rotated — please login again"}',
                                media_type="application/json")

            # Attach user context for downstream handlers
            user_id = self.token_manager.get_user_id(token)
            request.state.user_id = user_id
            request.state.token_manager = self.token_manager

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 100, window: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window
        self._requests = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        if client_ip not in self._requests:
            self._requests[client_ip] = []

        # Clean old entries
        self._requests[client_ip] = [
            t for t in self._requests[client_ip] if now - t < self.window
        ]

        if len(self._requests[client_ip]) >= self.max_requests:
            return Response(status_code=429, content="Rate limit exceeded. Try again later.")

        self._requests[client_ip].append(now)
        return await call_next(request)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start
        logger.info(
            "Request: %s %s -> %d (%.2fms)",
            request.method, request.url.path, response.status_code, duration * 1000,
        )
        return response
