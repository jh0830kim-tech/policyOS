"""Provider privacy, redaction, and transmission policy contracts."""

import re
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PrivacyModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DataClassification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    DENY_RESTRICTED = "deny_restricted"
    DENY_CONFIDENTIAL = "deny_confidential"
    DENY_ORGANIZATION = "deny_organization"
    DENY_PERMISSION = "deny_permission"
    DENY_PROVIDER = "deny_provider"
    DENY_CROSS_ORGANIZATION = "deny_cross_organization"


class ProviderTransmissionContext(PrivacyModel):
    organization_id: UUID
    authorized_organization_id: UUID
    user_id: UUID
    task_id: UUID
    data_classification: DataClassification = DataClassification.INTERNAL
    organization_allows_provider: bool = True
    user_can_execute: bool = True
    confidential_external_allowed: bool = False


class TransmissionDecision(PrivacyModel):
    allowed: bool
    decision: PolicyDecision


class ProviderTransmissionPolicy:
    def __init__(
        self,
        approved_providers: frozenset[str] = frozenset({"openai"}),
        *,
        allow_confidential_external_provider: bool = False,
    ) -> None:
        self._approved_providers = approved_providers
        self._allow_confidential_external_provider = allow_confidential_external_provider

    def evaluate(self, provider: str, context: ProviderTransmissionContext) -> TransmissionDecision:
        if context.organization_id != context.authorized_organization_id:
            return TransmissionDecision(
                allowed=False, decision=PolicyDecision.DENY_CROSS_ORGANIZATION
            )
        if provider not in self._approved_providers:
            return TransmissionDecision(allowed=False, decision=PolicyDecision.DENY_PROVIDER)
        if not context.organization_allows_provider:
            return TransmissionDecision(allowed=False, decision=PolicyDecision.DENY_ORGANIZATION)
        if not context.user_can_execute:
            return TransmissionDecision(allowed=False, decision=PolicyDecision.DENY_PERMISSION)
        if context.data_classification is DataClassification.RESTRICTED:
            return TransmissionDecision(allowed=False, decision=PolicyDecision.DENY_RESTRICTED)
        if context.data_classification is DataClassification.CONFIDENTIAL and not (
            context.confidential_external_allowed or self._allow_confidential_external_provider
        ):
            return TransmissionDecision(allowed=False, decision=PolicyDecision.DENY_CONFIDENTIAL)
        return TransmissionDecision(allowed=True, decision=PolicyDecision.ALLOW)


class RedactionResult(PrivacyModel):
    text: str
    redacted_item_count: int = Field(ge=0)

    @property
    def applied(self) -> bool:
        return self.redacted_item_count > 0


class Redactor(Protocol):
    def redact(self, text: str) -> RedactionResult: ...


class NoOpRedactor:
    def redact(self, text: str) -> RedactionResult:
        return RedactionResult(text=text, redacted_item_count=0)


class RegexRedactor:
    """Best-effort masker. It intentionally reports counts, never matched values."""

    _PATTERNS = (
        re.compile(r"(?i)\bsk-[a-z0-9_-]{16,}\b"),
        re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/-]+=*"),
        re.compile(r"\b\d{6}-?[1-4]\d{6}\b"),
        re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
        re.compile(r"(?<!\d)(?:\+?82[- ]?)?0?1[016789][- ]?\d{3,4}[- ]?\d{4}(?!\d)"),
        re.compile(r"(?<!\d)0\d{1,2}[- ]?\d{3,4}[- ]?\d{4}(?!\d)"),
        re.compile(r"(?i)\b(?:replace-with-[a-z0-9-]+|development-only-[a-z0-9-]+)\b"),
    )

    def __init__(self, custom_terms: tuple[str, ...] = ()) -> None:
        self._custom_patterns = tuple(
            re.compile(re.escape(term), re.IGNORECASE) for term in custom_terms if term.strip()
        )

    def redact(self, text: str) -> RedactionResult:
        redacted = text
        count = 0
        for pattern in (*self._PATTERNS, *self._custom_patterns):
            redacted, matches = pattern.subn("[REDACTED]", redacted)
            count += matches
        return RedactionResult(text=redacted, redacted_item_count=count)


class ProviderAuditMetadata(PrivacyModel):
    provider: str = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=200)
    organization_id: UUID
    user_id: UUID
    task_id: UUID
    data_classification: DataClassification
    redaction_applied: bool
    redacted_item_count: int = Field(ge=0)
    store_enabled: bool
    transmitted_at: datetime
    success: bool
    policy_decision: PolicyDecision
    error_code: str | None = Field(default=None, max_length=100)


class ProviderAuditSink(Protocol):
    async def record(self, metadata: ProviderAuditMetadata) -> None: ...


class NullProviderAuditSink:
    async def record(self, metadata: ProviderAuditMetadata) -> None:
        return None
