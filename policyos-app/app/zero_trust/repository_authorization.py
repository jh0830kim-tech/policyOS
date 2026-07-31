"""Independent final repository reauthorization and exact-use permits."""

import hashlib as _hashlib
import json as _json
from datetime import UTC as _UTC
from datetime import datetime
from enum import StrEnum
from typing import Protocol, TypeVar
from uuid import UUID

from pydantic import Field, field_validator

from app.ai.privacy import DataClassification
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware
from app.zero_trust.delegation import DelegatedExecutionContext
from app.zero_trust.errors import (
    AuthorizationVersionMismatchError,
    RepositoryAuthorizationError,
    RepositoryDecisionDigestError,
    RepositoryPermitError,
    RepositoryPermitReplayError,
    RepositoryRequestDigestError,
)


class RepositoryAuthorizationOutcome(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRES_HUMAN_APPROVAL = "requires_human_approval"


class RepositoryAuthorizationReason(StrEnum):
    ALLOWED_BY_POLICY = "allowed_by_policy"
    USER_INACTIVE = "user_inactive"
    MEMBERSHIP_MISSING = "membership_missing"
    MEMBERSHIP_INACTIVE = "membership_inactive"
    TENANT_MISMATCH = "tenant_mismatch"
    ORGANIZATION_MISMATCH = "organization_mismatch"
    USER_MISMATCH = "user_mismatch"
    RESOURCE_DENIED = "resource_denied"
    ACTION_DENIED = "action_denied"
    PURPOSE_DENIED = "purpose_denied"
    RISK_DENIED = "risk_denied"
    CLASSIFICATION_DENIED = "classification_denied"
    DELEGATION_INVALID = "delegation_invalid"
    SERVICE_ACTOR_MISMATCH = "service_actor_mismatch"
    AGENT_INSTANCE_MISMATCH = "agent_instance_mismatch"
    POLICY_REVISION_MISMATCH = "policy_revision_mismatch"
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"


class RepositoryAccessRequest(ExecutionModel):
    repository_request_id: UUID
    delegation_id: UUID
    tenant_id: UUID
    organization_id: UUID
    on_behalf_of_user_id: UUID
    service_actor_id: UUID
    agent_instance_id: UUID
    task_id: UUID
    repository_id: str = Field(min_length=1, max_length=200)
    resource_id: str = Field(min_length=1, max_length=200)
    resource_type: str = Field(min_length=1, max_length=100)
    action: str = Field(min_length=1, max_length=100)
    purpose: str = Field(min_length=1, max_length=100)
    risk_level: str = Field(min_length=1, max_length=50)
    classification: DataClassification
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "requested_at")


class RepositoryPolicyFacts(ExecutionModel):
    active_user: bool
    membership_exists: bool
    membership_active: bool
    membership_tenant_id: UUID | None
    membership_organization_id: UUID | None
    membership_user_id: UUID | None
    allowed_resource_ids: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    allowed_purposes: tuple[str, ...]
    allowed_risk_levels: tuple[str, ...]
    allowed_classifications: tuple[DataClassification, ...]
    delegation_valid: bool
    expected_service_actor_id: UUID
    expected_agent_instance_id: UUID
    repository_policy_revision: str = Field(min_length=1, max_length=200)
    requires_human_approval: bool = False

    @field_validator(
        "allowed_resource_ids",
        "allowed_actions",
        "allowed_purposes",
        "allowed_risk_levels",
        "allowed_classifications",
    )
    @classmethod
    def canonical(cls, value):
        if tuple(sorted(set(value), key=str)) != value:
            raise ValueError("repository policy facts must be canonical and unique")
        return value


class RepositoryAuthorizationDecision(ExecutionModel):
    repository_authorization_decision_id: UUID
    repository_request_id: UUID
    delegation_id: UUID
    outcome: RepositoryAuthorizationOutcome
    reason_codes: tuple[RepositoryAuthorizationReason, ...]
    repository_policy_revision: str
    decided_at: datetime

    @field_validator("reason_codes")
    @classmethod
    def canonical(cls, value):
        if not value or tuple(sorted(set(value), key=lambda item: item.value)) != value:
            raise RepositoryAuthorizationError("decision reasons must be canonical and non-empty")
        return value

    @field_validator("decided_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "decided_at")


def evaluate_repository_access_policy(
    request: RepositoryAccessRequest,
    delegation: DelegatedExecutionContext,
    facts: RepositoryPolicyFacts,
    *,
    repository_authorization_decision_id: UUID,
    decided_at: datetime,
) -> RepositoryAuthorizationDecision:
    reasons: list[RepositoryAuthorizationReason] = []
    if not facts.active_user:
        reasons.append(RepositoryAuthorizationReason.USER_INACTIVE)
    if not facts.membership_exists:
        reasons.append(RepositoryAuthorizationReason.MEMBERSHIP_MISSING)
    elif not facts.membership_active:
        reasons.append(RepositoryAuthorizationReason.MEMBERSHIP_INACTIVE)
    if facts.membership_tenant_id != request.tenant_id:
        reasons.append(RepositoryAuthorizationReason.TENANT_MISMATCH)
    if facts.membership_organization_id != request.organization_id:
        reasons.append(RepositoryAuthorizationReason.ORGANIZATION_MISMATCH)
    if facts.membership_user_id != request.on_behalf_of_user_id:
        reasons.append(RepositoryAuthorizationReason.USER_MISMATCH)
    if request.resource_id not in facts.allowed_resource_ids:
        reasons.append(RepositoryAuthorizationReason.RESOURCE_DENIED)
    if request.action not in facts.allowed_actions:
        reasons.append(RepositoryAuthorizationReason.ACTION_DENIED)
    if request.purpose not in facts.allowed_purposes:
        reasons.append(RepositoryAuthorizationReason.PURPOSE_DENIED)
    if request.risk_level not in facts.allowed_risk_levels:
        reasons.append(RepositoryAuthorizationReason.RISK_DENIED)
    if request.classification not in facts.allowed_classifications:
        reasons.append(RepositoryAuthorizationReason.CLASSIFICATION_DENIED)
    if not facts.delegation_valid:
        reasons.append(RepositoryAuthorizationReason.DELEGATION_INVALID)
    if request.service_actor_id != facts.expected_service_actor_id:
        reasons.append(RepositoryAuthorizationReason.SERVICE_ACTOR_MISMATCH)
    if request.agent_instance_id != facts.expected_agent_instance_id:
        reasons.append(RepositoryAuthorizationReason.AGENT_INSTANCE_MISMATCH)
    delegation_fields = (
        "delegation_id",
        "tenant_id",
        "organization_id",
        "on_behalf_of_user_id",
        "service_actor_id",
        "agent_instance_id",
        "task_id",
        "resource_id",
        "resource_type",
        "action",
        "purpose",
        "risk_level",
        "classification",
    )
    if any(getattr(request, field) != getattr(delegation, field) for field in delegation_fields):
        reasons.append(RepositoryAuthorizationReason.DELEGATION_INVALID)
    try:
        delegation.require_valid_at(request.requested_at)
    except ValueError:
        reasons.append(RepositoryAuthorizationReason.DELEGATION_INVALID)
    reasons = sorted(set(reasons), key=lambda item: item.value)
    if reasons:
        outcome = RepositoryAuthorizationOutcome.DENY
    elif facts.requires_human_approval:
        outcome = RepositoryAuthorizationOutcome.REQUIRES_HUMAN_APPROVAL
        reasons = [RepositoryAuthorizationReason.HUMAN_APPROVAL_REQUIRED]
    else:
        outcome = RepositoryAuthorizationOutcome.ALLOW
        reasons = [RepositoryAuthorizationReason.ALLOWED_BY_POLICY]
    return RepositoryAuthorizationDecision(
        repository_authorization_decision_id=repository_authorization_decision_id,
        repository_request_id=request.repository_request_id,
        delegation_id=request.delegation_id,
        outcome=outcome,
        reason_codes=tuple(reasons),
        repository_policy_revision=facts.repository_policy_revision,
        decided_at=decided_at,
    )


class AuthorizedRepositoryAccessPermit(ExecutionModel):
    repository_permit_id: UUID
    repository_request_id: UUID
    delegation_id: UUID
    repository_authorization_decision_id: UUID
    tenant_id: UUID
    organization_id: UUID
    on_behalf_of_user_id: UUID
    service_actor_id: UUID
    agent_instance_id: UUID
    task_id: UUID
    repository_id: str
    resource_id: str
    resource_type: str
    action: str
    purpose: str
    risk_level: str
    classification: DataClassification
    repository_policy_revision: str
    issued_at: datetime
    expires_at: datetime | None = None

    @field_validator("issued_at", "expires_at")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name)


def issue_repository_access_permit(
    request: RepositoryAccessRequest,
    decision: RepositoryAuthorizationDecision,
    *,
    repository_permit_id: UUID,
    issued_at: datetime,
    expires_at: datetime | None = None,
) -> AuthorizedRepositoryAccessPermit:
    if (
        decision.outcome is not RepositoryAuthorizationOutcome.ALLOW
        or decision.repository_request_id != request.repository_request_id
        or decision.delegation_id != request.delegation_id
    ):
        raise RepositoryPermitError("repository authorization did not allow exact request")
    if expires_at is not None and expires_at <= issued_at:
        raise RepositoryPermitError("repository permit expiry must follow issuance")
    return AuthorizedRepositoryAccessPermit(
        repository_permit_id=repository_permit_id,
        repository_request_id=request.repository_request_id,
        delegation_id=request.delegation_id,
        repository_authorization_decision_id=decision.repository_authorization_decision_id,
        tenant_id=request.tenant_id,
        organization_id=request.organization_id,
        on_behalf_of_user_id=request.on_behalf_of_user_id,
        service_actor_id=request.service_actor_id,
        agent_instance_id=request.agent_instance_id,
        task_id=request.task_id,
        repository_id=request.repository_id,
        resource_id=request.resource_id,
        resource_type=request.resource_type,
        action=request.action,
        purpose=request.purpose,
        risk_level=request.risk_level,
        classification=request.classification,
        repository_policy_revision=decision.repository_policy_revision,
        issued_at=issued_at,
        expires_at=expires_at,
    )


def validate_repository_access_permit(
    permit: AuthorizedRepositoryAccessPermit,
    request: RepositoryAccessRequest,
    *,
    repository_policy_revision: str,
    evaluated_at: datetime,
) -> None:
    evaluated_at = require_aware(evaluated_at, "evaluated_at")
    fields = (
        "repository_request_id",
        "delegation_id",
        "tenant_id",
        "organization_id",
        "on_behalf_of_user_id",
        "service_actor_id",
        "agent_instance_id",
        "task_id",
        "repository_id",
        "resource_id",
        "resource_type",
        "action",
        "purpose",
        "risk_level",
        "classification",
    )
    if any(getattr(permit, field) != getattr(request, field) for field in fields):
        raise RepositoryPermitError("repository permit lineage mismatch")
    if permit.repository_policy_revision != repository_policy_revision:
        raise RepositoryPermitError("repository policy revision mismatch")
    if evaluated_at < permit.issued_at or (
        permit.expires_at is not None and evaluated_at >= permit.expires_at
    ):
        raise RepositoryPermitError("repository permit is outside its lifetime")


ResultT = TypeVar("ResultT")


class RepositoryOperation(Protocol[ResultT]):
    def __call__(self, request: RepositoryAccessRequest) -> ResultT: ...


def execute_authorized_repository_operation[ResultT](
    request: RepositoryAccessRequest,
    permit: AuthorizedRepositoryAccessPermit,
    operation: RepositoryOperation[ResultT],
    *,
    repository_policy_revision: str,
    evaluated_at: datetime,
) -> ResultT:
    validate_repository_access_permit(
        permit,
        request,
        repository_policy_revision=repository_policy_revision,
        evaluated_at=evaluated_at,
    )
    return operation(request)


# Sprint 13 CP0.6 immutable request and decision lineage hardening.
class RepositoryPermitStatus(StrEnum):
    ISSUED = "issued"
    REVOKED = "revoked"
    EXPIRED = "expired"
    CONSUMED = "consumed"


class RepositoryRequestFacts(ExecutionModel):
    repository_request_id: UUID
    delegation_id: UUID
    lineage_id: UUID
    lineage_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    tenant_id: UUID
    organization_id: UUID
    on_behalf_of_user_id: UUID
    service_actor_id: UUID
    agent_instance_id: UUID
    task_id: UUID
    repository_id: str = Field(min_length=1, max_length=200)
    resource_id: str = Field(min_length=1, max_length=200)
    resource_type: str = Field(min_length=1, max_length=100)
    action: str = Field(min_length=1, max_length=100)
    purpose: str = Field(min_length=1, max_length=100)
    risk_level: str = Field(min_length=1, max_length=50)
    classification: DataClassification
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def aware_requested_at(cls, value):
        return require_aware(value, "requested_at")


_REPOSITORY_REQUEST_FIELDS = tuple(RepositoryRequestFacts.model_fields)


def _canonical_metadata(values):
    normalized = {}
    for key, value in values:
        if isinstance(value, datetime):
            normalized[key] = (
                require_aware(value, key)
                .astimezone(_UTC)
                .isoformat(timespec="microseconds")
                .replace("+00:00", "Z")
            )
        elif isinstance(value, UUID):
            normalized[key] = str(value)
        elif isinstance(value, StrEnum):
            normalized[key] = value.value
        elif isinstance(value, tuple):
            normalized[key] = [
                item.value if isinstance(item, StrEnum) else str(item) for item in value
            ]
        else:
            normalized[key] = value
    return _json.dumps(
        normalized, ensure_ascii=False, separators=(",", ":"), sort_keys=False
    ).encode("utf-8")


def canonicalize_repository_request(facts: RepositoryRequestFacts) -> bytes:
    return _canonical_metadata(
        tuple((field, getattr(facts, field)) for field in _REPOSITORY_REQUEST_FIELDS)
    )


class RepositoryRequestDigest(ExecutionModel):
    digest_algorithm: str = Field(default="sha256", pattern=r"^sha256$")
    digest_version: str = Field(default="repository_request_digest_v1", max_length=100)
    digest_value: str = Field(pattern=r"^[0-9a-f]{64}$")


def compute_repository_request_digest(facts: RepositoryRequestFacts) -> RepositoryRequestDigest:
    return RepositoryRequestDigest(
        digest_value=_hashlib.sha256(canonicalize_repository_request(facts)).hexdigest()
    )


def verify_repository_request_digest(
    facts: RepositoryRequestFacts, digest: RepositoryRequestDigest
) -> None:
    if compute_repository_request_digest(facts).digest_value != digest.digest_value:
        raise RepositoryRequestDigestError("repository request digest mismatch")


class RepositoryAuthorizationDecisionFacts(ExecutionModel):
    repository_authorization_decision_id: UUID
    repository_request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome: RepositoryAuthorizationOutcome
    reason_codes: tuple[RepositoryAuthorizationReason, ...]
    policy_revision: str = Field(min_length=1, max_length=200)
    authorization_engine_id: str = Field(min_length=1, max_length=200)
    authorization_engine_version: str = Field(min_length=1, max_length=100)
    authorization_rule_set_id: str = Field(min_length=1, max_length=200)
    authorization_rule_set_version: str = Field(min_length=1, max_length=100)
    decided_at: datetime

    @field_validator("reason_codes")
    @classmethod
    def canonical_decision_reasons(cls, value):
        if not value or tuple(sorted(set(value), key=lambda item: item.value)) != value:
            raise RepositoryDecisionDigestError("decision reasons must be canonical")
        return value

    @field_validator("decided_at")
    @classmethod
    def aware_decided_at(cls, value):
        return require_aware(value, "decided_at")


_DECISION_FIELDS = tuple(RepositoryAuthorizationDecisionFacts.model_fields)


def canonicalize_repository_authorization_decision(
    facts: RepositoryAuthorizationDecisionFacts,
) -> bytes:
    return _canonical_metadata(tuple((field, getattr(facts, field)) for field in _DECISION_FIELDS))


class RepositoryAuthorizationDecisionDigest(ExecutionModel):
    digest_algorithm: str = Field(default="sha256", pattern=r"^sha256$")
    digest_version: str = Field(default="repository_decision_digest_v1", max_length=100)
    digest_value: str = Field(pattern=r"^[0-9a-f]{64}$")


def compute_repository_authorization_decision_digest(
    facts: RepositoryAuthorizationDecisionFacts,
) -> RepositoryAuthorizationDecisionDigest:
    return RepositoryAuthorizationDecisionDigest(
        digest_value=_hashlib.sha256(
            canonicalize_repository_authorization_decision(facts)
        ).hexdigest()
    )


def verify_repository_authorization_decision_digest(
    facts: RepositoryAuthorizationDecisionFacts,
    digest: RepositoryAuthorizationDecisionDigest,
) -> None:
    expected = compute_repository_authorization_decision_digest(facts)
    if expected.digest_value != digest.digest_value:
        raise RepositoryDecisionDigestError("repository decision digest mismatch")


class ReplayProtectedRepositoryAccessPermit(AuthorizedRepositoryAccessPermit):
    repository_request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    delegation_lineage_id: UUID
    delegation_lineage_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    authorization_engine_id: str = Field(min_length=1, max_length=200)
    authorization_engine_version: str = Field(min_length=1, max_length=100)
    authorization_rule_set_id: str = Field(min_length=1, max_length=200)
    authorization_rule_set_version: str = Field(min_length=1, max_length=100)
    policy_revision: str = Field(min_length=1, max_length=200)
    decision_facts_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    permit_revision: int = Field(ge=1)
    permit_status: RepositoryPermitStatus


def issue_replay_protected_repository_permit(
    request: RepositoryAccessRequest,
    decision: RepositoryAuthorizationDecision,
    request_facts: RepositoryRequestFacts,
    request_digest: RepositoryRequestDigest,
    decision_facts: RepositoryAuthorizationDecisionFacts,
    decision_digest: RepositoryAuthorizationDecisionDigest,
    *,
    repository_permit_id: UUID,
    permit_revision: int,
    issued_at: datetime,
    expires_at: datetime | None = None,
) -> ReplayProtectedRepositoryAccessPermit:
    verify_repository_request_digest(request_facts, request_digest)
    verify_repository_authorization_decision_digest(decision_facts, decision_digest)
    if request_facts.repository_request_id != request.repository_request_id:
        raise RepositoryPermitReplayError("repository request facts identity mismatch")
    if decision_facts.repository_request_digest != request_digest.digest_value:
        raise RepositoryDecisionDigestError("decision does not bind repository request")
    base = issue_repository_access_permit(
        request,
        decision,
        repository_permit_id=repository_permit_id,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    return ReplayProtectedRepositoryAccessPermit(
        **base.model_dump(),
        repository_request_digest=request_digest.digest_value,
        delegation_lineage_id=request_facts.lineage_id,
        delegation_lineage_digest=request_facts.lineage_digest,
        authorization_engine_id=decision_facts.authorization_engine_id,
        authorization_engine_version=decision_facts.authorization_engine_version,
        authorization_rule_set_id=decision_facts.authorization_rule_set_id,
        authorization_rule_set_version=decision_facts.authorization_rule_set_version,
        policy_revision=decision_facts.policy_revision,
        decision_facts_digest=decision_digest.digest_value,
        permit_revision=permit_revision,
        permit_status=RepositoryPermitStatus.ISSUED,
    )


def validate_repository_permit_for_request(
    permit: ReplayProtectedRepositoryAccessPermit,
    request_facts: RepositoryRequestFacts,
    request_digest: RepositoryRequestDigest,
    *,
    lineage_id: UUID,
    lineage_digest: str,
    authorization_engine_id: str,
    authorization_engine_version: str,
    authorization_rule_set_id: str,
    authorization_rule_set_version: str,
    policy_revision: str,
    decision_facts_digest: str,
    evaluated_at: datetime,
) -> None:
    verify_repository_request_digest(request_facts, request_digest)
    exact = (
        permit.repository_request_id,
        permit.repository_request_digest,
        permit.delegation_lineage_id,
        permit.delegation_lineage_digest,
        permit.tenant_id,
        permit.organization_id,
        permit.on_behalf_of_user_id,
        permit.agent_instance_id,
        permit.task_id,
        permit.repository_id,
        permit.resource_id,
        permit.action,
        permit.purpose,
        permit.policy_revision,
        permit.decision_facts_digest,
    )
    expected = (
        request_facts.repository_request_id,
        request_digest.digest_value,
        lineage_id,
        lineage_digest,
        request_facts.tenant_id,
        request_facts.organization_id,
        request_facts.on_behalf_of_user_id,
        request_facts.agent_instance_id,
        request_facts.task_id,
        request_facts.repository_id,
        request_facts.resource_id,
        request_facts.action,
        request_facts.purpose,
        policy_revision,
        decision_facts_digest,
    )
    if exact != expected:
        raise RepositoryPermitReplayError("repository permit substitution detected")
    versions = (
        permit.authorization_engine_id,
        permit.authorization_engine_version,
        permit.authorization_rule_set_id,
        permit.authorization_rule_set_version,
    )
    expected_versions = (
        authorization_engine_id,
        authorization_engine_version,
        authorization_rule_set_id,
        authorization_rule_set_version,
    )
    if versions != expected_versions:
        raise AuthorizationVersionMismatchError("authorization version metadata mismatch")
    if permit.permit_status is not RepositoryPermitStatus.ISSUED:
        raise RepositoryPermitReplayError("repository permit status is not issued")
    evaluated_at = require_aware(evaluated_at, "evaluated_at")
    if evaluated_at < permit.issued_at or (
        permit.expires_at is not None and evaluated_at >= permit.expires_at
    ):
        raise RepositoryPermitReplayError("repository permit is outside its lifetime")


def execute_replay_protected_repository_operation[ResultT](
    permit: ReplayProtectedRepositoryAccessPermit,
    request_facts: RepositoryRequestFacts,
    request_digest: RepositoryRequestDigest,
    operation: RepositoryOperation[ResultT],
    request: RepositoryAccessRequest,
    **validation_facts,
) -> ResultT:
    validate_repository_permit_for_request(
        permit, request_facts, request_digest, **validation_facts
    )
    return operation(request)
