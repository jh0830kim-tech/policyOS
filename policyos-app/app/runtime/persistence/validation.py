"""Fail-closed scope and revision validation for CP7 persistence."""

from datetime import datetime

from app.runtime.persistence.errors import RuntimePersistenceConflictError
from app.runtime.persistence.serialization import (
    RuntimePersistenceRecord,
    RuntimePersistenceRecordMetadata,
    metadata_for,
)
from app.runtime.ports import (
    RuntimePortClassificationError,
    RuntimePortScopeError,
    RuntimePortTimestampError,
    RuntimeRepositoryReadRequest,
    RuntimeRepositoryWriteRequest,
)


def _aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RuntimePortTimestampError(f"{field} must be timezone-aware")


def validate_persistence_read_request(
    request: RuntimeRepositoryReadRequest,
) -> RuntimeRepositoryReadRequest:
    _aware(request.requested_at, "requested_at")
    return request


def validate_persistence_write(
    record: RuntimePersistenceRecord,
    request: RuntimeRepositoryWriteRequest,
    *,
    stored_at: datetime,
) -> RuntimePersistenceRecordMetadata:
    metadata = metadata_for(record)
    if (metadata.record_id, metadata.tenant_id, metadata.organization_id) != (
        request.record_id,
        request.tenant_id,
        request.organization_id,
    ):
        raise RuntimePortScopeError("persistence write crosses record or tenant scope")
    if metadata.classification is not request.classification:
        raise RuntimePortClassificationError(
            "persistence write classification must exactly match the record"
        )
    if (
        metadata.intrinsic_revision is not None
        and metadata.intrinsic_revision != request.resulting_revision
    ):
        raise RuntimePersistenceConflictError(
            "persistence revision differs from the immutable record revision"
        )
    _aware(stored_at, "stored_at")
    if stored_at < request.requested_at:
        raise RuntimePortTimestampError("persistence storage time predates write request")
    return metadata


def validate_loaded_record(
    metadata: RuntimePersistenceRecordMetadata,
    request: RuntimeRepositoryReadRequest,
    *,
    stored_revision: int,
) -> None:
    if (metadata.record_id, metadata.tenant_id, metadata.organization_id) != (
        request.record_id,
        request.tenant_id,
        request.organization_id,
    ):
        raise RuntimePortScopeError("stored runtime record crosses requested scope")
    if metadata.classification is not request.classification:
        raise RuntimePortClassificationError(
            "stored runtime record classification differs from read boundary"
        )
    if request.expected_revision is not None and stored_revision != request.expected_revision:
        raise RuntimePersistenceConflictError("stored runtime revision differs from expectation")


__all__ = (
    "validate_loaded_record",
    "validate_persistence_read_request",
    "validate_persistence_write",
)
