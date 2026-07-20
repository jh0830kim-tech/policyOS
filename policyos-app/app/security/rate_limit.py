"""Deterministic tenant/action rate limiting boundary."""

from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID


class SecurityRateLimitError(RuntimeError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Security rate limit exceeded")
        self.retry_after_seconds = retry_after_seconds


class RateLimitPolicy(Protocol):
    def check(self, user_id: UUID, organization_id: UUID, action: str, limit: int) -> None: ...


class InMemoryRateLimiter:
    def __init__(self, window_seconds: int = 60, clock=None) -> None:
        self.window = window_seconds
        self.clock = clock or (lambda: datetime.now(UTC))
        self.events = defaultdict(deque)

    def check(self, user_id: UUID, organization_id: UUID, action: str, limit: int) -> None:
        now = self.clock()
        key = (organization_id, user_id, action)
        cutoff = now - timedelta(seconds=self.window)
        queue = self.events[key]
        while queue and queue[0] <= cutoff:
            queue.popleft()
        if len(queue) >= limit:
            raise SecurityRateLimitError(
                max(1, int((queue[0] + timedelta(seconds=self.window) - now).total_seconds()))
            )
        queue.append(now)


class DisabledRateLimiter:
    def check(self, user_id: UUID, organization_id: UUID, action: str, limit: int) -> None:
        return None
