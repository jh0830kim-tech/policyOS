"""Strict transport-safe schemas for the future CP9 Runtime API."""

from pydantic import BaseModel, ConfigDict

from app.ai.privacy import DataClassification
from app.services.runtime_api_contracts import (
    BoundedMessage,
    BoundedReference,
    IdempotencyKey,
    RuntimeApiErrorCode,
    RuntimeApiPublicStatus,
)


class RuntimeApiTransportModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class RuntimeInvocationSubmitRequest(RuntimeApiTransportModel):
    action_reference: BoundedReference
    command_reference: BoundedReference
    input_reference: BoundedReference | None = None
    classification: DataClassification
    idempotency_key: IdempotencyKey


class RuntimeInvocationStatusQuery(RuntimeApiTransportModel):
    invocation_reference: BoundedReference


class RuntimeReconciliationRequest(RuntimeApiTransportModel):
    invocation_reference: BoundedReference
    reconciliation_reference: BoundedReference
    idempotency_key: IdempotencyKey


class RuntimeStatusResponse(RuntimeApiTransportModel):
    invocation_reference: BoundedReference
    status: RuntimeApiPublicStatus
    status_reference: BoundedReference
    correlation_reference: BoundedReference


class RuntimeReconciliationResponse(RuntimeApiTransportModel):
    invocation_reference: BoundedReference
    status: RuntimeApiPublicStatus
    reconciliation_reference: BoundedReference
    correlation_reference: BoundedReference


class RuntimePublicErrorEnvelope(RuntimeApiTransportModel):
    code: RuntimeApiErrorCode
    message: BoundedMessage
    retryable: bool
    correlation_reference: BoundedReference | None = None


__all__ = (
    "RuntimeInvocationStatusQuery",
    "RuntimeInvocationSubmitRequest",
    "RuntimePublicErrorEnvelope",
    "RuntimeReconciliationRequest",
    "RuntimeReconciliationResponse",
    "RuntimeStatusResponse",
)
