"""Safe fallback decisions for provider failures and incomplete results."""

from __future__ import annotations

from enum import StrEnum

from app.knowledge.providers.domain import ProviderModel
from app.knowledge.providers.errors import (
    KnowledgeProviderAuthenticationError,
    KnowledgeProviderError,
    KnowledgeProviderPolicyDeniedError,
    KnowledgeProviderSecurityError,
)


class ProviderFallbackReason(StrEnum):
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    RATE_LIMIT = "rate_limit"
    DISABLED = "disabled"
    CAPABILITY = "capability_unavailable"
    EMPTY = "empty_result"
    TEMPORAL = "temporal_mismatch"
    CITATION = "incomplete_citation"
    STALE = "stale_only"
    PROHIBITED = "fallback_prohibited"
    MAXIMUM = "maximum_attempts"


class ProviderFallbackDecision(ProviderModel):
    allowed: bool
    reason: ProviderFallbackReason
    next_provider: str | None = None


class ProviderFallbackPolicy:
    def __init__(self, max_attempts: int = 3) -> None:
        if max_attempts < 0:
            raise ValueError("max_attempts must not be negative")
        self.max_attempts = max_attempts

    def decide(
        self,
        *,
        error: KnowledgeProviderError | None = None,
        response=None,
        candidates: tuple[str, ...],
        attempted: tuple[str, ...],
        allow_empty: bool = True,
        explicit_provider_only: bool = False,
    ) -> ProviderFallbackDecision:
        if explicit_provider_only or isinstance(
            error,
            (
                KnowledgeProviderAuthenticationError,
                KnowledgeProviderPolicyDeniedError,
                KnowledgeProviderSecurityError,
            ),
        ):
            return ProviderFallbackDecision(allowed=False, reason=ProviderFallbackReason.PROHIBITED)
        if len(attempted) >= self.max_attempts:
            return ProviderFallbackDecision(allowed=False, reason=ProviderFallbackReason.MAXIMUM)
        if response is not None and not response.evidence and not allow_empty:
            return ProviderFallbackDecision(allowed=False, reason=ProviderFallbackReason.PROHIBITED)
        reason = ProviderFallbackReason.EMPTY if response is not None else self._reason(error)
        next_provider = next((name for name in candidates if name not in attempted), None)
        return ProviderFallbackDecision(
            allowed=next_provider is not None,
            reason=reason,
            next_provider=next_provider,
        )

    @staticmethod
    def _reason(error):
        code = getattr(error, "code", "")
        if "timeout" in code:
            return ProviderFallbackReason.TIMEOUT
        if "rate" in code:
            return ProviderFallbackReason.RATE_LIMIT
        if "disabled" in code:
            return ProviderFallbackReason.DISABLED
        if "unsupported" in code:
            return ProviderFallbackReason.CAPABILITY
        return ProviderFallbackReason.UNAVAILABLE
