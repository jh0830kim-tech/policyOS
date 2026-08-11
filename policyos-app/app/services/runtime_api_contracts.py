"""Immutable contracts for the CP9 trusted Runtime application boundary."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.runtime.ports import (
    RuntimeApiActiveTransactionContext,
    RuntimeApiLocalWriteSetOperation,
    RuntimeApiLocalWriteSetStage,
    RuntimeApiPersistenceBindingRead,
)

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
    PARTIALLY_COMPLETED = "partially_completed"
    CANCELLATION_PENDING = "cancellation_pending"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    COMPENSATION_REQUIRED = "compensation_required"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    INVALIDATED = "invalidated"


class RuntimeApiResultCardinality(StrEnum):
    EXACTLY_ZERO = "exactly_zero"
    ZERO_OR_ONE = "zero_or_one"
    EXACTLY_ONE = "exactly_one"


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


class RuntimeApiSubmissionBindingFacts(RuntimeApiModel):
    persistence: RuntimeApiPersistenceBindingRead


class RuntimeApiInvocationQueryBindingFacts(RuntimeApiModel):
    persistence: RuntimeApiPersistenceBindingRead


class RuntimeApiReconciliationBindingFacts(RuntimeApiModel):
    persistence: RuntimeApiPersistenceBindingRead


class RuntimeApiSubmissionIntegrationFacts(RuntimeApiModel):
    binding: RuntimeApiSubmissionBindingFacts
    active_transaction: RuntimeApiActiveTransactionContext
    stage: RuntimeApiLocalWriteSetStage
    command_id: UUID
    command_version: CommandVersion
    command_digest: BoundedDigest
    action_reference: BoundedReference
    command_reference: BoundedReference
    correlation_reference: BoundedReference
    classification: DataClassification
    tenant_id: UUID
    organization_id: UUID
    root_lineage_id: UUID
    root_lineage_digest_reference: BoundedReference

    @model_validator(mode="after")
    def exact_closed_submission(self):
        if self.stage.operation is not RuntimeApiLocalWriteSetOperation.SUBMIT_INVOCATION:
            raise ValueError("submission integration requires submit_invocation stage")
        if self.stage.binding != self.binding.persistence:
            raise ValueError("submission integration persistence binding differs")
        scope = self.binding.persistence.scope
        if (
            self.tenant_id,
            self.organization_id,
            self.classification,
            self.root_lineage_id,
            self.root_lineage_digest_reference,
        ) != (
            scope.tenant_id,
            scope.organization_id,
            scope.classification,
            scope.root_lineage_id,
            scope.root_lineage_digest_reference,
        ):
            raise ValueError("submission integration scope or lineage differs")
        return self


class RuntimeApiInvocationQueryIntegrationFacts(RuntimeApiModel):
    binding: RuntimeApiInvocationQueryBindingFacts
    active_transaction: RuntimeApiActiveTransactionContext
    query_id: UUID
    invocation_reference: BoundedReference
    correlation_reference: BoundedReference
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: BoundedReference

    @model_validator(mode="after")
    def exact_read_scope(self):
        scope = self.binding.persistence.scope
        if (
            self.tenant_id,
            self.organization_id,
            self.classification,
            self.root_lineage_id,
            self.root_lineage_digest_reference,
        ) != (
            scope.tenant_id,
            scope.organization_id,
            scope.classification,
            scope.root_lineage_id,
            scope.root_lineage_digest_reference,
        ):
            raise ValueError("query integration scope or lineage differs")
        return self


class RuntimeApiReconciliationIntegrationFacts(RuntimeApiModel):
    binding: RuntimeApiReconciliationBindingFacts
    active_transaction: RuntimeApiActiveTransactionContext
    stage: RuntimeApiLocalWriteSetStage
    command_id: UUID
    command_version: CommandVersion
    command_digest: BoundedDigest
    invocation_reference: BoundedReference
    reconciliation_reference: BoundedReference
    correlation_reference: BoundedReference
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: BoundedReference

    @model_validator(mode="after")
    def exact_closed_reconciliation(self):
        if self.stage.operation is not RuntimeApiLocalWriteSetOperation.REQUEST_RECONCILIATION:
            raise ValueError("reconciliation integration requires request_reconciliation stage")
        if self.stage.binding != self.binding.persistence:
            raise ValueError("reconciliation integration persistence binding differs")
        scope = self.binding.persistence.scope
        if (
            self.tenant_id,
            self.organization_id,
            self.classification,
            self.root_lineage_id,
            self.root_lineage_digest_reference,
        ) != (
            scope.tenant_id,
            scope.organization_id,
            scope.classification,
            scope.root_lineage_id,
            scope.root_lineage_digest_reference,
        ):
            raise ValueError("reconciliation integration scope or lineage differs")
        return self


class RuntimeApiSubmissionFacts(RuntimeApiModel):
    command_id: UUID
    command_version: CommandVersion
    receipt_id: UUID
    committed_at: datetime
    correlation_reference: BoundedReference
    context: RuntimeApiTrustedContextFacts
    integration: RuntimeApiSubmissionIntegrationFacts

    @field_validator("committed_at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("committed_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def exact_integration_identity(self):
        if (
            self.command_id,
            self.command_version,
            self.receipt_id,
            self.correlation_reference,
        ) != (
            self.integration.command_id,
            self.integration.command_version,
            self.integration.stage.transport_receipt_id,
            self.integration.correlation_reference,
        ):
            raise ValueError("submission outer and integration facts differ")
        return self


class RuntimeApiInvocationQueryFacts(RuntimeApiModel):
    query_id: UUID
    requested_at: datetime
    correlation_reference: BoundedReference
    context: RuntimeApiTrustedContextFacts
    integration: RuntimeApiInvocationQueryIntegrationFacts

    @field_validator("requested_at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("requested_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def exact_integration_identity(self):
        if (self.query_id, self.correlation_reference) != (
            self.integration.query_id,
            self.integration.correlation_reference,
        ):
            raise ValueError("query outer and integration facts differ")
        return self


class RuntimeApiReconciliationFacts(RuntimeApiModel):
    command_id: UUID
    command_version: CommandVersion
    receipt_id: UUID
    committed_at: datetime
    correlation_reference: BoundedReference
    context: RuntimeApiTrustedContextFacts
    integration: RuntimeApiReconciliationIntegrationFacts

    @field_validator("committed_at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("committed_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def exact_integration_identity(self):
        if (
            self.command_id,
            self.command_version,
            self.receipt_id,
            self.correlation_reference,
        ) != (
            self.integration.command_id,
            self.integration.command_version,
            self.integration.stage.transport_receipt_id,
            self.integration.correlation_reference,
        ):
            raise ValueError("reconciliation outer and integration facts differ")
        return self


class RuntimeApiSubmissionCommand(RuntimeApiModel):
    identity: RuntimeApiCommandIdentity
    principal: RuntimeApiTrustedPrincipal
    scope: RuntimeApiTrustedScope
    permission: RuntimeApiPermissionFact
    action_reference: BoundedReference
    command_reference: BoundedReference
    input_reference: BoundedReference | None = None
    classification: DataClassification
    integration: RuntimeApiSubmissionIntegrationFacts


class RuntimeApiInvocationQuery(RuntimeApiModel):
    query_id: UUID
    principal: RuntimeApiTrustedPrincipal
    scope: RuntimeApiTrustedScope
    permission: RuntimeApiPermissionFact
    invocation_reference: BoundedReference
    correlation_reference: BoundedReference
    integration: RuntimeApiInvocationQueryIntegrationFacts


class RuntimeApiReconciliationCommand(RuntimeApiModel):
    identity: RuntimeApiCommandIdentity
    principal: RuntimeApiTrustedPrincipal
    scope: RuntimeApiTrustedScope
    permission: RuntimeApiPermissionFact
    invocation_reference: BoundedReference
    reconciliation_reference: BoundedReference
    integration: RuntimeApiReconciliationIntegrationFacts


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
    "RuntimeApiInvocationQueryIntegrationFacts",
    "RuntimeApiInvocationQueryInput",
    "RuntimeApiInvocationQuery",
    "RuntimeApiModel",
    "RuntimeApiOperation",
    "RuntimeApiOrganizationSelector",
    "RuntimeApiPermission",
    "RuntimeApiPermissionFact",
    "RuntimeApiPublicStatus",
    "RuntimeApiResultCardinality",
    "RuntimeApiReconciliationCommand",
    "RuntimeApiReconciliationBindingFacts",
    "RuntimeApiReconciliationFacts",
    "RuntimeApiReconciliationIntegrationFacts",
    "RuntimeApiReconciliationInput",
    "RuntimeApiReconciliationResult",
    "RuntimeApiSafeError",
    "RuntimeApiSafeResult",
    "RuntimeApiStatusProjection",
    "RuntimeApiSubmissionCommand",
    "RuntimeApiSubmissionBindingFacts",
    "RuntimeApiSubmissionFacts",
    "RuntimeApiSubmissionIntegrationFacts",
    "RuntimeApiSubmissionInput",
    "RuntimeApiSubmissionResult",
    "RuntimeApiTrustedPrincipal",
    "RuntimeApiTrustedContextFacts",
    "RuntimeApiTrustedScope",
)
