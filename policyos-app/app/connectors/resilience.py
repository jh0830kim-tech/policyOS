"""Retry policy helpers for connector transport resilience."""

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 2
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 2.0
    jitter_factor: float = 0.1

    def delay_for(self, attempt: int) -> float:
        if attempt <= 0:
            return 0.0
        base = min(self.base_delay_seconds * (2 ** (attempt - 1)), self.max_delay_seconds)
        jitter = random.uniform(0, self.jitter_factor * base)
        return base + jitter
