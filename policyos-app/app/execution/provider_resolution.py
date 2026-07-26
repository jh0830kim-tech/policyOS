"""Pure deterministic provider resolution and safe dispatch binding contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.execution.domain import ExecutionContext, ExecutionModel
from app.execution.provider_errors import (
    BindingExpiredError,
    BindingIdentityMismatchError,
    DispatchBindingError,
    DuplicateProviderError,
    NoEligibleProviderError,
    ProviderAvailabilityError,
    ProviderDecisionError,
    ProviderPolicyError,
    UnknownProviderError,
)
from app.execution.runtime import DispatchRequest, ExecutionSession
from app.execution.validation import require_aware, require_not_lower, validate_json

_PROVIDER_ID = r"^[a-z][a-z0-9_]{0,39}(?:\.[a-z][a-z0-9_]{0,39}){1,4}$"
_CAPABILITY_ID = r"^[a-z][a-z0-9_]{0,39}(?:\.[a-z][a-z0-9_]{0,39}){1,4}$"
_SAFE_ID = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$"
_REASON = r"^[a-z][a-z0-9_]{1,99}$"
_MAX_PROVIDERS = 500


class ProviderKind(StrEnum):
    KNOWLEDGE = "knowledge"
    CONNECTOR = "connector"
    INTERNAL_TOOL = "internal_tool"
    MCP = "mcp"


class AvailabilityStatus(StrEnum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class CapacityState(StrEnum):
    NORMAL = "normal"
    CONSTRAINED = "constrained"
    EXHAUSTED = "exhausted"
    UNKNOWN = "unknown"


class ProviderCapability(ExecutionModel):
    capability_id: str = Field(pattern=_CAPABILITY_ID)
    enabled: bool = True
    priority_override: int | None = Field(default=None, ge=0, le=10_000)
    maximum_input_classification: DataClassification = DataClassification.RESTRICTED
    supports_citations: bool = False
    supports_structured_output: bool = False
    operation_version: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,49}$"
    )


class ProviderDescriptor(ExecutionModel):
    provider_id: str = Field(pattern=_PROVIDER_ID)
    provider_kind: ProviderKind
    capabilities: tuple[ProviderCapability, ...]
    minimum_classification: DataClassification = DataClassification.PUBLIC
    maximum_classification: DataClassification = DataClassification.RESTRICTED
    allowed_organization_ids: tuple[UUID, ...] = ()
    denied_organization_ids: tuple[UUID, ...] = ()
    priority: int = Field(default=100, ge=0, le=10_000)
    cost_tier: int = Field(default=0, ge=0, le=10)
    latency_tier: int = Field(default=0, ge=0, le=10)
    reliability_tier: int = Field(default=0, ge=0, le=10)
    supports_streaming: bool = False
    supports_idempotency: bool = False
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("provider_id")
    @classmethod
    def safe_logical_provider_id(cls, value):
        if value.split(".", 1)[0] in {"http", "https", "ftp", "file"}:
            raise ValueError("provider ID must not encode an endpoint")
        forbidden = {"credential", "password", "secret", "token"}
        if any(part in forbidden for part in value.split(".")):
            raise ValueError("provider ID must not encode secret material")
        return value

    @field_validator("capabilities")
    @classmethod
    def canonical_capabilities(cls, value):
        ids = [item.capability_id for item in value]
        if not value or len(ids) != len(set(ids)):
            raise ValueError("provider capabilities must be non-empty and unique")
        if ids != sorted(ids):
            raise ValueError("provider capabilities must use canonical ordering")
        return value

    @field_validator("allowed_organization_ids", "denied_organization_ids")
    @classmethod
    def canonical_organizations(cls, value):
        if len(value) > 100 or list(value) != sorted(set(value), key=str):
            raise ValueError("organization IDs must be unique and canonically ordered")
        return value

    @field_validator("metadata")
    @classmethod
    def safe_metadata(cls, value):
        return validate_json(value, field="provider metadata")

    @model_validator(mode="after")
    def valid_scope(self) -> Self:
        require_not_lower(self.maximum_classification, self.minimum_classification)
        if set(self.allowed_organization_ids) & set(self.denied_organization_ids):
            raise ValueError("organization allow and deny lists must not overlap")
        return self

    def capability(self, capability_id: str) -> ProviderCapability | None:
        return next(
            (item for item in self.capabilities if item.capability_id == capability_id), None
        )


class ProviderCatalog(ExecutionModel):
    providers: tuple[ProviderDescriptor, ...]

    @field_validator("providers")
    @classmethod
    def canonical_providers(cls, value):
        ids = [item.provider_id for item in value]
        if len(value) > _MAX_PROVIDERS:
            raise ValueError("provider catalog exceeds limit")
        if len(ids) != len(set(ids)):
            raise DuplicateProviderError("Provider catalog contains a duplicate provider ID")
        if ids != sorted(ids):
            raise ValueError("providers must use canonical ordering")
        return value

    @classmethod
    def from_providers(cls, providers) -> ProviderCatalog:
        return cls(providers=tuple(sorted(providers, key=lambda item: item.provider_id)))

    def all(self) -> tuple[ProviderDescriptor, ...]:
        return self.providers

    def get(self, provider_id: str) -> ProviderDescriptor | None:
        return next((item for item in self.providers if item.provider_id == provider_id), None)

    def require(self, provider_id: str) -> ProviderDescriptor:
        provider = self.get(provider_id)
        if provider is None:
            raise UnknownProviderError("Provider catalog does not contain the requested provider")
        return provider

    def providers_for_capability(self, capability_id: str) -> tuple[ProviderDescriptor, ...]:
        return tuple(item for item in self.providers if item.capability(capability_id) is not None)


class ProviderAvailability(ExecutionModel):
    provider_id: str = Field(pattern=_PROVIDER_ID)
    status: AvailabilityStatus
    observed_at: datetime
    valid_until: datetime | None = None
    reason_code: str | None = Field(default=None, pattern=_REASON)
    capacity_state: CapacityState = CapacityState.UNKNOWN

    @field_validator("observed_at", "valid_until")
    @classmethod
    def aware_times(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def valid_window(self) -> Self:
        if self.valid_until is not None and self.valid_until < self.observed_at:
            raise ProviderAvailabilityError("Availability validity cannot precede observation")
        return self


class ProviderAvailabilitySnapshot(ExecutionModel):
    entries: tuple[ProviderAvailability, ...] = ()

    @field_validator("entries")
    @classmethod
    def canonical_entries(cls, value):
        ids = [item.provider_id for item in value]
        if len(value) > _MAX_PROVIDERS or len(ids) != len(set(ids)):
            raise ProviderAvailabilityError("Availability snapshot is duplicate or oversized")
        if ids != sorted(ids):
            raise ValueError("availability entries must use canonical ordering")
        return value

    @classmethod
    def from_entries(cls, entries) -> ProviderAvailabilitySnapshot:
        return cls(entries=tuple(sorted(entries, key=lambda item: item.provider_id)))

    def get(self, provider_id: str) -> ProviderAvailability | None:
        return next((item for item in self.entries if item.provider_id == provider_id), None)


class ProviderRequirement(ExecutionModel):
    capability_id: str = Field(pattern=_CAPABILITY_ID)
    classification: DataClassification
    organization_id: UUID
    actor_id: UUID
    required_citations: bool = False
    required_structured_output: bool = False
    required_idempotency: bool = False
    maximum_cost_tier: int | None = Field(default=None, ge=0, le=10)
    maximum_latency_tier: int | None = Field(default=None, ge=0, le=10)
    preferred_provider_ids: tuple[str, ...] = ()
    excluded_provider_ids: tuple[str, ...] = ()
    policy_id: str = Field(pattern=_SAFE_ID)
    execution_id: UUID
    step_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.-]{0,99}$")
    required: bool = True

    @field_validator("preferred_provider_ids", "excluded_provider_ids")
    @classmethod
    def canonical_provider_ids(cls, value):
        if len(value) > 100 or tuple(sorted(set(value))) != value:
            raise ValueError("provider IDs must be unique and canonically ordered")
        for provider_id in value:
            if not __import__("re").fullmatch(_PROVIDER_ID, provider_id):
                raise ValueError("provider ID is invalid")
        return value

    @model_validator(mode="after")
    def valid_preferences(self) -> Self:
        if set(self.preferred_provider_ids) & set(self.excluded_provider_ids):
            raise ProviderPolicyError("Preferred and excluded provider IDs must not overlap")
        return self

    def validate_dispatch(self, dispatch: DispatchRequest) -> None:
        if (
            self.capability_id != dispatch.capability_id
            or self.execution_id != dispatch.execution_id
            or self.step_id != dispatch.step_id
            or self.organization_id != dispatch.organization_id
            or self.actor_id != dispatch.actor_id
        ):
            raise BindingIdentityMismatchError("Provider requirement does not match dispatch scope")
        require_not_lower(self.classification, dispatch.classification)
        require_not_lower(dispatch.classification, self.classification)


class ProviderSelectionPolicy(ExecutionModel):
    policy_id: str = Field(pattern=_SAFE_ID)
    selection_version: str = Field(default="1", pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,49}$")
    allow_degraded: bool = False
    allow_unknown_availability: bool = False
    require_enabled: bool = True
    prefer_lower_cost: bool = True
    prefer_lower_latency: bool = True
    prefer_higher_reliability: bool = True
    preferred_provider_ids: tuple[str, ...] = ()
    excluded_provider_ids: tuple[str, ...] = ()
    fallback_allowed: bool = True
    maximum_candidates: int = Field(default=100, ge=1, le=500)

    @model_validator(mode="after")
    def valid_ids(self) -> Self:
        preferred = tuple(sorted(set(self.preferred_provider_ids)))
        excluded = tuple(sorted(set(self.excluded_provider_ids)))
        if preferred != self.preferred_provider_ids or excluded != self.excluded_provider_ids:
            raise ProviderPolicyError("Policy provider IDs must be canonical and unique")
        if set(preferred) & set(excluded):
            raise ProviderPolicyError("Policy preferred and excluded IDs must not overlap")
        return self


class ProviderCandidate(ExecutionModel):
    provider_id: str = Field(pattern=_PROVIDER_ID)
    eligible: bool
    rank: tuple[int | str, ...]
    reason_codes: tuple[str, ...] = ()
    availability_status: AvailabilityStatus
    capability_id: str = Field(pattern=_CAPABILITY_ID)
    classification_supported: bool
    organization_allowed: bool

    @field_validator("reason_codes")
    @classmethod
    def safe_reasons(cls, value):
        if len(value) > 20 or len(value) != len(set(value)):
            raise ValueError("candidate reasons must be bounded and unique")
        return value


class ProviderSelectionDecision(ExecutionModel):
    capability_id: str = Field(pattern=_CAPABILITY_ID)
    selected_provider_id: str | None = Field(default=None, pattern=_PROVIDER_ID)
    candidates: tuple[ProviderCandidate, ...]
    policy_id: str = Field(pattern=_SAFE_ID)
    selection_version: str
    deterministic_rank: tuple[int | str, ...] | None = None
    warnings: tuple[str, ...] = ()
    evaluated_at: datetime
    execution_id: UUID
    step_id: str

    @field_validator("evaluated_at")
    @classmethod
    def aware_evaluated_at(cls, value):
        return require_aware(value, "evaluated_at")

    @model_validator(mode="after")
    def valid_selection(self) -> Self:
        eligible = [item for item in self.candidates if item.eligible]
        if eligible and self.selected_provider_id != eligible[0].provider_id:
            raise ProviderDecisionError("Selected provider must be the first eligible candidate")
        if not eligible and self.selected_provider_id is not None:
            raise ProviderDecisionError("Unbound decision cannot select a provider")
        if self.selected_provider_id is not None and self.deterministic_rank != eligible[0].rank:
            raise ProviderDecisionError("Decision rank does not match selected provider")
        return self


class ProviderResolver(Protocol):
    def resolve(self, requirement, catalog, availability, policy, evaluated_at): ...


class DeterministicProviderResolver:
    def resolve(
        self,
        requirement: ProviderRequirement,
        catalog: ProviderCatalog,
        availability: ProviderAvailabilitySnapshot | None,
        policy: ProviderSelectionPolicy,
        evaluated_at: datetime,
    ) -> ProviderSelectionDecision:
        require_aware(evaluated_at, "evaluated_at")
        if requirement.policy_id != policy.policy_id:
            raise ProviderPolicyError("Requirement and selection policy identities do not match")
        candidates = [
            _candidate(provider, requirement, availability, policy, evaluated_at)
            for provider in catalog.all()
        ]
        candidates.sort(key=lambda item: (not item.eligible, item.rank))
        candidates = candidates[: policy.maximum_candidates]
        eligible = [item for item in candidates if item.eligible]
        if eligible and not policy.fallback_allowed:
            candidates = [eligible[0]] + [item for item in candidates if not item.eligible]
        if not eligible and requirement.required:
            raise NoEligibleProviderError(
                f"No eligible provider for capability {requirement.capability_id} "
                f"at step {requirement.step_id}"
            )
        selected = eligible[0] if eligible else None
        return ProviderSelectionDecision(
            capability_id=requirement.capability_id,
            selected_provider_id=selected.provider_id if selected else None,
            candidates=tuple(candidates),
            policy_id=policy.policy_id,
            selection_version=policy.selection_version,
            deterministic_rank=selected.rank if selected else None,
            warnings=() if selected else ("optional_capability_unavailable",),
            evaluated_at=evaluated_at,
            execution_id=requirement.execution_id,
            step_id=requirement.step_id,
        )


def _candidate(provider, requirement, snapshot, policy, evaluated_at) -> ProviderCandidate:
    reasons: list[str] = []
    capability = provider.capability(requirement.capability_id)
    if capability is None or not capability.enabled:
        reasons.append("capability_not_supported")
    if policy.require_enabled and not provider.enabled:
        reasons.append("provider_disabled")
    availability = snapshot.get(provider.provider_id) if snapshot else None
    status = availability.status if availability else AvailabilityStatus.UNKNOWN
    if availability and availability.valid_until and evaluated_at >= availability.valid_until:
        reasons.append("availability_stale")
        status = AvailabilityStatus.UNKNOWN
    elif status in {AvailabilityStatus.UNAVAILABLE, AvailabilityStatus.DISABLED}:
        reasons.append("provider_unavailable")
    elif status is AvailabilityStatus.DEGRADED and not policy.allow_degraded:
        reasons.append("provider_degraded")
    elif status is AvailabilityStatus.UNKNOWN and not policy.allow_unknown_availability:
        reasons.append("availability_unknown")
    classification_supported = _classification_supported(provider, capability, requirement)
    if not classification_supported:
        reasons.append("classification_not_supported")
    organization_allowed = requirement.organization_id not in provider.denied_organization_ids and (
        not provider.allowed_organization_ids
        or requirement.organization_id in provider.allowed_organization_ids
    )
    if not organization_allowed:
        reasons.append("organization_not_allowed")
    if capability and requirement.required_citations and not capability.supports_citations:
        reasons.append("required_citations_not_supported")
    if (
        capability
        and requirement.required_structured_output
        and not capability.supports_structured_output
    ):
        reasons.append("required_structured_output_not_supported")
    if requirement.required_idempotency and not provider.supports_idempotency:
        reasons.append("required_idempotency_not_supported")
    excluded = set(requirement.excluded_provider_ids) | set(policy.excluded_provider_ids)
    if provider.provider_id in excluded:
        reasons.append("excluded_by_policy")
    if (
        requirement.maximum_cost_tier is not None
        and provider.cost_tier > requirement.maximum_cost_tier
    ):
        reasons.append("cost_limit_exceeded")
    if (
        requirement.maximum_latency_tier is not None
        and provider.latency_tier > requirement.maximum_latency_tier
    ):
        reasons.append("latency_limit_exceeded")
    preferred = set(requirement.preferred_provider_ids) | set(policy.preferred_provider_ids)
    availability_rank = {AvailabilityStatus.AVAILABLE: 0, AvailabilityStatus.DEGRADED: 1}.get(
        status, 2
    )
    priority = (
        capability.priority_override
        if capability and capability.priority_override is not None
        else provider.priority
    )
    rank = (
        0 if provider.provider_id in preferred else 1,
        availability_rank,
        priority,
        -provider.reliability_tier if policy.prefer_higher_reliability else 0,
        provider.latency_tier if policy.prefer_lower_latency else 0,
        provider.cost_tier if policy.prefer_lower_cost else 0,
        provider.provider_id,
    )
    return ProviderCandidate(
        provider_id=provider.provider_id,
        eligible=not reasons,
        rank=rank,
        reason_codes=tuple(reasons),
        availability_status=status,
        capability_id=requirement.capability_id,
        classification_supported=classification_supported,
        organization_allowed=organization_allowed,
    )


def _classification_supported(provider, capability, requirement) -> bool:
    if capability is None:
        return False
    try:
        require_not_lower(requirement.classification, provider.minimum_classification)
        require_not_lower(provider.maximum_classification, requirement.classification)
        require_not_lower(capability.maximum_input_classification, requirement.classification)
    except ValueError:
        return False
    return True


class DispatchBinding(ExecutionModel):
    binding_id: UUID
    dispatch_id: UUID
    session_id: UUID
    execution_id: UUID
    plan_id: UUID
    step_id: str
    capability_id: str = Field(pattern=_CAPABILITY_ID)
    provider_id: str = Field(pattern=_PROVIDER_ID)
    provider_kind: ProviderKind
    policy_id: str = Field(pattern=_SAFE_ID)
    selection_version: str
    idempotency_key: str = Field(pattern=_SAFE_ID)
    bound_at: datetime
    deadline: datetime | None = None
    classification: DataClassification
    organization_id: UUID

    @field_validator("bound_at", "deadline")
    @classmethod
    def aware_times(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def valid_deadline(self) -> Self:
        if self.deadline is not None and self.bound_at >= self.deadline:
            raise BindingExpiredError("Dispatch binding deadline has expired")
        return self


def bind_dispatch(
    dispatch: DispatchRequest,
    session: ExecutionSession,
    context: ExecutionContext,
    requirement: ProviderRequirement,
    decision: ProviderSelectionDecision,
    catalog: ProviderCatalog,
    *,
    binding_id: UUID,
    bound_at: datetime,
    idempotency_key: str,
) -> DispatchBinding:
    require_aware(bound_at, "bound_at")
    requirement.validate_dispatch(dispatch)
    identities = (
        dispatch.session_id == session.session_id
        and dispatch.execution_id
        == session.execution_id
        == context.execution_id
        == decision.execution_id
        and dispatch.plan_id == session.plan_id
        and dispatch.step_id == decision.step_id == requirement.step_id
        and dispatch.organization_id == session.organization_id == context.organization_id
        and dispatch.actor_id == session.actor_id == context.actor_id
        and dispatch.capability_id == decision.capability_id == requirement.capability_id
        and dispatch.correlation_id == session.correlation_id == context.correlation_id
    )
    if not identities:
        raise BindingIdentityMismatchError("Dispatch binding identities are inconsistent")
    if decision.policy_id != requirement.policy_id or decision.selected_provider_id is None:
        raise DispatchBindingError("Provider decision cannot be bound")
    provider = catalog.require(decision.selected_provider_id)
    candidate = next(
        (item for item in decision.candidates if item.provider_id == provider.provider_id), None
    )
    if (
        candidate is None
        or not candidate.eligible
        or provider.capability(dispatch.capability_id) is None
    ):
        raise DispatchBindingError("Selected provider is not eligible for dispatch")
    if dispatch.deadline is not None and bound_at >= dispatch.deadline:
        raise BindingExpiredError("Dispatch deadline has expired")
    return DispatchBinding(
        binding_id=binding_id,
        dispatch_id=dispatch.dispatch_id,
        session_id=dispatch.session_id,
        execution_id=dispatch.execution_id,
        plan_id=dispatch.plan_id,
        step_id=dispatch.step_id,
        capability_id=dispatch.capability_id,
        provider_id=provider.provider_id,
        provider_kind=provider.provider_kind,
        policy_id=decision.policy_id,
        selection_version=decision.selection_version,
        idempotency_key=idempotency_key,
        bound_at=bound_at,
        deadline=dispatch.deadline,
        classification=dispatch.classification,
        organization_id=dispatch.organization_id,
    )


def korean_law_mcp_descriptor() -> ProviderDescriptor:
    """Return a static descriptor without importing or constructing the live MCP provider."""
    return ProviderDescriptor(
        provider_id="knowledge.korean_law_mcp",
        provider_kind=ProviderKind.MCP,
        capabilities=(
            ProviderCapability(
                capability_id="knowledge.legal_search",
                supports_citations=True,
                supports_structured_output=True,
                operation_version="1",
            ),
        ),
        priority=100,
        reliability_tier=5,
        supports_idempotency=True,
        metadata={"legacy_provider_name": "korean-law-mcp"},
    )
