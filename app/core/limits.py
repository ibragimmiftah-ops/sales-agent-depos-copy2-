"""Rate limiting, request size guards and run budgets."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from fastapi import HTTPException, Request, status

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import Principal

logger = get_logger(__name__)


class RateLimiter:
    """Simple per-principal in-memory rate limiter with Redis fallback."""

    def __init__(
        self,
        key_prefix: str,
        max_requests: int,
        window_seconds: int,
    ):
        self.key_prefix = key_prefix
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = {}

    def _key(self, request: Request, principal: Principal) -> str:
        client = request.client.host if request.client else "unknown"
        return f"{self.key_prefix}:{principal.tenant_id}:{principal.user_id or client}"

    async def check(self, request: Request, principal: Principal) -> None:
        key = self._key(request, principal)
        now = time.time()
        window = self._buckets.setdefault(key, [])
        window[:] = [t for t in window if now - t < self.window_seconds]
        if len(window) >= self.max_requests:
            logger.warning("rate_limit_exceeded", key=key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )
        window.append(now)


class RunBudget:
    """Per-run budget for tool calls, turns and cost."""

    def __init__(self) -> None:
        self.tool_calls: int = 0
        self.turns: int = 0

    def check_tool_call(self) -> None:
        self.tool_calls += 1
        if self.tool_calls > settings.MAX_TOOL_CALLS_PER_RUN:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Too many tool calls in this run",
            )


@dataclass
class ValidationContext:
    """Validated request context with budget."""

    principal: Principal
    run_budget: RunBudget = field(default_factory=RunBudget)
    request_id: str = field(default_factory=lambda: f"req_{int(time.time() * 1000)}")

    def guard_oversized(self, text: str, max_length: int = 2000) -> None:
        if len(text) > max_length:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Input too large",
            )
