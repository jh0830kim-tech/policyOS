"""Immutable contracts for the CP9 trusted Runtime application boundary."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ai.privacy import DataClassification
from app.runtime.ports import RuntimeApiPersistenceBindingRead

BoundedReference = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}$")]
BoundedDigest = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.:-]{15,199}$")]
BoundedMessage = Annotated[str, Field(min_length=1, max_length=300)]
IdempotencyKey = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,99}$")]
CommandVersion = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]{1,40}$")]


class RuntimeApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class RuntimeApiPermission(StrEnum):
    READ = "runtime.read"
    INVOKE = "runtime.invoke"
    RECONCILE = "runtime.reconcile"


class RuntimeApiOrganizationSelector(RuntimeApiModel):
    organization_id: UUID


class RuntimeApiOperation(StrEnum):
    SUBMIT_INVOCATION = "submit_invocation"
    GET_INVOCATION = "get_invocation"
    REQUEST_RECONCILIATION = "request_reconciliation"


class RuntimeApiIdempotencyDisposition(StrEnum):
    COMMITTED = "committed"
    EXACT_REPLAY = "exact_replay"


class RuntimeApiPublicStatus(StrEnum):
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    AMBIGUOUS = "ambiguous"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    DEAD_LETTERED = "dead_lettered"


class RuntimeApiErrorCode(StrEnum):
    UNAUTHENTICATED = "runtime_unauthenticated"
    PRINCIPAL_INACTIVE = "runtime_principal_inactive"
    SCOPE_NOT_FOUND = "runtime_scope_not_found"
    PERMISSION_DENIED = "runtime_permission_denied"
    INVALID_REQUEST = "runtime_invalid_request"
    IDEMPOTENCY_CONFLICT = "runtime_idempotency_conflict"
    AUTHORITY_DENIED = "runtime_authority_denied"
    STATE_CONFLICT = "runtime_state_conflict"
    REGISTRY_CONFLICT = "runtime_registry_conflict"
    RATE_LIMITED = "runtime_rate_limited"
    DEPENDENCY_UNAVAILABLE = "runtime_dependency_unavailable"
    INTERNAL_FAILURE = "runtime_internal_failure"


class RuntimeApiTrustedPrincipal(RuntimeApiModel):
    principal_id: UUID
    user_id: UUID
    token_subject: BoundedReference
    token_jti_reference: BoundedReference
    verified_issuer: BoundedReference
    verified_audiences: tuple[BoundedReference, ...] = Field(min_length=1, max_length=8)
    active_principal_reference: BoundedReference
    authenticated_at: datetime
    authentication_reference: BoundedReference

    @field_validator("authenticated_at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("authenticated_at must be timezone-aware")
        return value


class RuntimeApiTrustedScope(RuntimeApiModel):
    tenant_id: UUID
    organization_id: UUID
    membership_id: UUID
    classification_ceiling: DataClassification
    scope_binding_reference: BoundedReference
    validated_at: datetime
    validation_reference: BoundedReference

    @field_validator("validated_at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("validated_at must be timezone-aware")
        return value


class RuntimeApiPermissionFact(RuntimeApiModel):
    permission: RuntimeApiPermission
    principal_id: UUID
    membership_id: UUID
    organization_id: UUID
    permission_reference: BoundedReference


class RuntimeApiCommandIdentity(RuntimeApiModel):
    command_id: UUID
    operation: RuntimeApiOperation
    tenant_id: UUID
    organization_id: UUID
    principal_id: UUID
    command_version: CommandVersion
    idempotency_key: IdempotencyKey
    command_digest: BoundedDigest
    correlation_reference: BoundedReference


class RuntimeApiSubmissionInput(RuntimeApiModel):
    action_reference: BoundedReference
    command_reference: BoundedReference
    input_reference: BoundedReference | None = None
    classification: DataClassification
    idempotency_key: IdempotencyKey


class RuntimeApiInvocationQueryInput(RuntimeApiModel):
    invocation_reference: BoundedReference


class RuntimeApiReconciliationInput(RuntimeApiModel):
    invocation_reference: BoundedReference
    reconciliation_reference: BoundedReference
    idempotency_key: IdempotencyKey


class RuntimeApiTrustedContextFacts(RuntimeApiModel):
    authentication_reference: BoundedReference
    validation_reference: BoundedReference
    authenticated_at: datetime
    validated_at: datetime

    @field_validator("authenticated_at", "validated_at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("trusted context times must be timezone-aware")
        return value


class RuntimeApiSubmissionFacts(RuntimeApiModel):
    command_id: UUID
    command_version: CommandVersion
    receipt_id: UUID
    committed_at: datetime
    correlation_reference: BoundedReference
    context: RuntimeApiTrustedContextFacts

    @field_validator("committed_at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("committed_at must be timezone-aware")
        return value


class RuntimeApiInvocationQueryFacts(RuntimeApiModel):
    query_id: UUID
    requested_at: datetime
    correlation_reference: BoundedReference
    context: RuntimeApiTrustedContextFacts

    @field_validator("requested_at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("requested_at must be timezone-aware")
        return value


class RuntimeApiReconciliationFacts(RuntimeApiModel):
    command_id: UUID
    command_version: CommandVersion
    receipt_id: UUID
    committed_at: datetime
    correlation_reference: BoundedReference
    context: RuntimeApiTrustedContextFacts

    @field_validator("committed_at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("committed_at must be timezone-aware")
        return value


class RuntimeApiSubmissionBindingFacts(RuntimeApiModel):
    persistence: RuntimeApiPersistenceBindingRead


class RuntimeApiInvocationQueryBindingFacts(RuntimeApiModel):
    persistence: RuntimeApiPersistenceBindingRead


class RuntimeApiReconciliationBindingFacts(RuntimeApiModel):
    persistence: RuntimeApiPersistenceBindingRead


class RuntimeApiSubmissionCommand(RuntimeApiModel):
    identity: RuntimeApiCommandIdentity
    principal: RuntimeApiTrustedPrincipal
    scope: RuntimeApiTrustedScope
    permission: RuntimeApiPermissionFact
    action_reference: BoundedReference
    command_reference: BoundedReference
    input_reference: BoundedReference | None = None
    classification: DataClassification


class RuntimeApiInvocationQuery(RuntimeApiModel):
    query_id: UUID
    principal: RuntimeApiTrustedPrincipal
    scope: RuntimeApiTrustedScope
    permission: RuntimeApiPermissionFact
    invocation_reference: BoundedReference
    correlation_reference: BoundedReference


class RuntimeApiReconciliationCommand(RuntimeApiModel):
    identity: RuntimeApiCommandIdentity
    principal: RuntimeApiTrustedPrincipal
    scope: RuntimeApiTrustedScope
    permission: RuntimeApiPermissionFact
    invocation_reference: BoundedReference
    reconciliation_reference: BoundedReference


class RuntimeApiStatusProjection(RuntimeApiModel):
    invocation_reference: BoundedReference
    status: RuntimeApiPublicStatus
    status_reference: BoundedReference
    correlation_reference: BoundedReference
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        return value


class RuntimeApiSafeResult(RuntimeApiModel):
    result_reference: BoundedReference
    projection: RuntimeApiStatusProjection


class RuntimeApiIdempotencyReceipt(RuntimeApiModel):
    receipt_id: UUID
    identity: RuntimeApiCommandIdentity
    safe_result: RuntimeApiSafeResult
    committed_at: datetime

    @field_validator("committed_at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("committed_at must be timezone-aware")
        return value


class RuntimeApiIdempotencyCommitFacts(RuntimeApiModel):
    receipt_id: UUID
    committed_at: datetime

    @field_validator("committed_at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("committed_at must be timezone-aware")
        return value


class RuntimeApiIdempotencyCommitResult(RuntimeApiModel):
    disposition: RuntimeApiIdempotencyDisposition
    receipt: RuntimeApiIdempotencyReceipt
    safe_result: RuntimeApiSafeResult


class RuntimeApiSubmissionResult(RuntimeApiModel):
    idempotency: RuntimeApiIdempotencyCommitResult


class RuntimeApiReconciliationResult(RuntimeApiModel):
    idempotency: RuntimeApiIdempotencyCommitResult


class RuntimeApiSafeError(RuntimeApiModel):
    code: RuntimeApiErrorCode
    message: BoundedMessage
    retryable: bool
    correlation_reference: BoundedReference | None = None


class RuntimeApiContractConflict(ValueError):
    """A bounded CP9 contract binding or replay conflict."""


__all__ = (
    "BoundedDigest",
    "BoundedMessage",
    "BoundedReference",
    "CommandVersion",
    "IdempotencyKey",
    "RuntimeApiCommandIdentity",
    "RuntimeApiContractConflict",
    "RuntimeApiErrorCode",
    "RuntimeApiIdempotencyCommitFacts",
    "RuntimeApiIdempotencyCommitResult",
    "RuntimeApiIdempotencyDisposition",
    "RuntimeApiIdempotencyReceipt",
    "RuntimeApiInvocationQueryFacts",
    "RuntimeApiInvocationQueryBindingFacts",
    "RuntimeApiInvocationQueryInput",
    "RuntimeApiInvocationQuery",
    "RuntimeApiModel",
    "RuntimeApiOperation",
    "RuntimeApiOrganizationSelector",
    "RuntimeApiPermission",
    "RuntimeApiPermissionFact",
    "RuntimeApiPublicStatus",
    "RuntimeApiReconciliationCommand",
    "RuntimeApiReconciliationBindingFacts",
    "RuntimeApiReconciliationFacts",
    "RuntimeApiReconciliationInput",
    "RuntimeApiReconciliationResult",
    "RuntimeApiSafeError",
    "RuntimeApiSafeResult",
    "RuntimeApiStatusProjection",
    "RuntimeApiSubmissionCommand",
    "RuntimeApiSubmissionBindingFacts",
    "RuntimeApiSubmissionFacts",
    "RuntimeApiSubmissionInput",
    "RuntimeApiSubmissionResult",
    "RuntimeApiTrustedPrincipal",
    "RuntimeApiTrustedContextFacts",
    "RuntimeApiTrustedScope",
)
