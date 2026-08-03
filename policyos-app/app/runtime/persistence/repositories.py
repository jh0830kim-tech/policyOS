"""SQLAlchemy repositories implementing the stable Runtime Ports contracts."""

from datetime import datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.runtime.audit import RuntimeAuditTrail
from app.runtime.authority import (
    RuntimeAuthorityBundle,
    RuntimeExecutionRequest,
    RuntimePermitReference,
)
from app.runtime.persistence.errors import (
    RuntimePersistenceConflictError,
    RuntimePersistenceError,
)
from app.runtime.persistence.models import RuntimeRecordHead, RuntimeRecordRevision
from app.runtime.persistence.serialization import (
    RuntimePersistenceRecord,
    RuntimePersistenceRecordMetadata,
    RuntimePersistenceRecordType,
    deserialize_runtime_record,
    metadata_for,
    serialize_runtime_record,
)
from app.runtime.persistence.validation import (
    validate_loaded_record,
    validate_persistence_read_request,
    validate_persistence_write,
)
from app.runtime.planning import ExecutionPlan
from app.runtime.ports import (
    RuntimeAdapterInvocationResult,
    RuntimeIdempotencyReservation,
    RuntimeOutboxEnqueueRecord,
    RuntimeRepositoryReadRequest,
    RuntimeRepositoryWriteReceipt,
    RuntimeRepositoryWriteRequest,
    validate_runtime_repository_write_receipt,
)
from app.runtime.state import RuntimeExecutionStateRecord


def _head_query(
    metadata: RuntimePersistenceRecordMetadata,
):
    return (
        select(RuntimeRecordHead)
        .where(
            RuntimeRecordHead.record_type == metadata.record_type.value,
            RuntimeRecordHead.tenant_id == metadata.tenant_id,
            RuntimeRecordHead.organization_id == metadata.organization_id,
            RuntimeRecordHead.record_id == metadata.record_id,
        )
        .with_for_update()
    )


async def persist_runtime_revision(
    session: AsyncSession,
    record: RuntimePersistenceRecord,
    *,
    receipt_id,
    write_request_id,
    transaction_id,
    expected_revision: int | None,
    resulting_revision: int,
    digest_reference: str,
    requested_at: datetime,
    stored_at: datetime,
) -> RuntimePersistenceRecordMetadata:
    """Write one immutable revision and advance its tenant-scoped head."""

    metadata = metadata_for(record)
    head = (await session.execute(_head_query(metadata))).scalar_one_or_none()
    if head is None:
        if expected_revision is not None or resulting_revision != 1:
            raise RuntimePersistenceConflictError(
                "first runtime persistence revision must be caller-supplied revision one"
            )
        head = RuntimeRecordHead(
            runtime_record_head_id=receipt_id,
            record_type=metadata.record_type.value,
            record_id=metadata.record_id,
            tenant_id=metadata.tenant_id,
            organization_id=metadata.organization_id,
            classification=metadata.classification.value,
            current_revision=resulting_revision,
            current_receipt_id=receipt_id,
            current_digest_reference=digest_reference,
            updated_at=stored_at,
        )
        session.add(head)
    else:
        if head.current_revision != expected_revision:
            raise RuntimePersistenceConflictError(
                "runtime persistence optimistic revision does not match"
            )
        if head.classification != metadata.classification.value:
            raise RuntimePersistenceConflictError(
                "runtime persistence classification cannot change across revisions"
            )
        if resulting_revision != head.current_revision + 1:
            raise RuntimePersistenceConflictError(
                "runtime persistence revision must advance exactly once"
            )
        head.current_revision = resulting_revision
        head.current_receipt_id = receipt_id
        head.current_digest_reference = digest_reference
        head.updated_at = stored_at

    session.add(
        RuntimeRecordRevision(
            runtime_repository_write_receipt_id=receipt_id,
            runtime_repository_write_request_id=write_request_id,
            runtime_transaction_id=transaction_id,
            record_type=metadata.record_type.value,
            record_id=metadata.record_id,
            tenant_id=metadata.tenant_id,
            organization_id=metadata.organization_id,
            classification=metadata.classification.value,
            record_revision=resulting_revision,
            record_digest_reference=digest_reference,
            payload=serialize_runtime_record(record),
            runtime_execution_request_id=metadata.runtime_execution_request_id,
            execution_plan_step_id=metadata.execution_plan_step_id,
            attempt_id=metadata.attempt_id,
            action_definition_id=metadata.action_definition_id,
            action=metadata.action,
            action_version=metadata.action_version,
            idempotency_key=metadata.idempotency_key,
            requested_at=requested_at,
            stored_at=stored_at,
        )
    )
    await session.flush()
    return metadata


class _SQLAlchemyRuntimeRepository[RecordT: RuntimePersistenceRecord]:
    def __init__(
        self,
        session: AsyncSession,
        *,
        record_type: RuntimePersistenceRecordType,
    ) -> None:
        self._session = session
        self._record_type = record_type

    async def get(self, request: RuntimeRepositoryReadRequest) -> RecordT | None:
        validate_persistence_read_request(request)
        revision = request.expected_revision
        if revision is None:
            head = (
                await self._session.execute(
                    select(RuntimeRecordHead).where(
                        RuntimeRecordHead.record_type == self._record_type.value,
                        RuntimeRecordHead.tenant_id == request.tenant_id,
                        RuntimeRecordHead.organization_id == request.organization_id,
                        RuntimeRecordHead.record_id == request.record_id,
                        RuntimeRecordHead.classification == request.classification.value,
                    )
                )
            ).scalar_one_or_none()
            if head is None:
                return None
            revision = head.current_revision
        stored = (
            await self._session.execute(
                select(RuntimeRecordRevision).where(
                    RuntimeRecordRevision.record_type == self._record_type.value,
                    RuntimeRecordRevision.tenant_id == request.tenant_id,
                    RuntimeRecordRevision.organization_id == request.organization_id,
                    RuntimeRecordRevision.record_id == request.record_id,
                    RuntimeRecordRevision.record_revision == revision,
                    RuntimeRecordRevision.classification == request.classification.value,
                )
            )
        ).scalar_one_or_none()
        if stored is None:
            return None
        record = deserialize_runtime_record(self._record_type, stored.payload)
        validate_loaded_record(metadata_for(record), request, stored_revision=revision)
        return cast(RecordT, record)

    async def _save(
        self,
        record: RecordT,
        request: RuntimeRepositoryWriteRequest,
        *,
        stored_at: datetime,
    ) -> RuntimeRepositoryWriteReceipt:
        metadata = validate_persistence_write(record, request, stored_at=stored_at)
        if metadata.record_type is not self._record_type:
            raise RuntimePersistenceError("repository received a different record type")
        try:
            async with self._session.begin_nested():
                await persist_runtime_revision(
                    self._session,
                    record,
                    receipt_id=request.runtime_repository_write_receipt_id,
                    write_request_id=request.runtime_repository_write_request_id,
                    transaction_id=None,
                    expected_revision=request.expected_revision,
                    resulting_revision=request.resulting_revision,
                    digest_reference=request.record_digest_reference,
                    requested_at=request.requested_at,
                    stored_at=stored_at,
                )
        except IntegrityError as exc:
            raise RuntimePersistenceConflictError(
                "runtime persistence uniqueness constraint conflicted"
            ) from exc
        except SQLAlchemyError as exc:
            raise RuntimePersistenceError("runtime repository storage failed") from exc
        receipt = RuntimeRepositoryWriteReceipt(
            runtime_repository_write_receipt_id=request.runtime_repository_write_receipt_id,
            runtime_repository_write_request_id=request.runtime_repository_write_request_id,
            record_id=request.record_id,
            record_revision=request.resulting_revision,
            record_digest_reference=request.record_digest_reference,
            tenant_id=request.tenant_id,
            organization_id=request.organization_id,
            classification=request.classification,
            stored_at=stored_at,
        )
        return validate_runtime_repository_write_receipt(request, receipt)


class SQLAlchemyExecutionRequestRepository(
    _SQLAlchemyRuntimeRepository[RuntimeExecutionRequest]
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, record_type=RuntimePersistenceRecordType.EXECUTION_REQUEST)

    save = _SQLAlchemyRuntimeRepository._save


class SQLAlchemyRuntimeAdmissionRepository(
    _SQLAlchemyRuntimeRepository[RuntimeAuthorityBundle]
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, record_type=RuntimePersistenceRecordType.AUTHORITY_BUNDLE)

    save = _SQLAlchemyRuntimeRepository._save


class SQLAlchemyExecutionPlanRepository(_SQLAlchemyRuntimeRepository[ExecutionPlan]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, record_type=RuntimePersistenceRecordType.EXECUTION_PLAN)

    save = _SQLAlchemyRuntimeRepository._save


class SQLAlchemyExecutionStateRepository(
    _SQLAlchemyRuntimeRepository[RuntimeExecutionStateRecord]
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, record_type=RuntimePersistenceRecordType.EXECUTION_STATE)

    save = _SQLAlchemyRuntimeRepository._save


class SQLAlchemyExecutionResultRepository(
    _SQLAlchemyRuntimeRepository[RuntimeAdapterInvocationResult]
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, record_type=RuntimePersistenceRecordType.EXECUTION_RESULT)

    save = _SQLAlchemyRuntimeRepository._save


class SQLAlchemyRuntimeAuditRepository(_SQLAlchemyRuntimeRepository[RuntimeAuditTrail]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, record_type=RuntimePersistenceRecordType.AUDIT_TRAIL)

    save = _SQLAlchemyRuntimeRepository._save


class SQLAlchemyRuntimePermitRepository(
    _SQLAlchemyRuntimeRepository[RuntimePermitReference]
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, record_type=RuntimePersistenceRecordType.PERMIT_REFERENCE)

    save = _SQLAlchemyRuntimeRepository._save


class SQLAlchemyRuntimeIdempotencyRepository(
    _SQLAlchemyRuntimeRepository[RuntimeIdempotencyReservation]
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(
            session, record_type=RuntimePersistenceRecordType.IDEMPOTENCY_RESERVATION
        )

    reserve = _SQLAlchemyRuntimeRepository._save


class SQLAlchemyRuntimeOutboxRepository(
    _SQLAlchemyRuntimeRepository[RuntimeOutboxEnqueueRecord]
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, record_type=RuntimePersistenceRecordType.OUTBOX_ENQUEUE)

    enqueue = _SQLAlchemyRuntimeRepository._save


__all__ = (
    "SQLAlchemyExecutionPlanRepository",
    "SQLAlchemyExecutionRequestRepository",
    "SQLAlchemyExecutionResultRepository",
    "SQLAlchemyExecutionStateRepository",
    "SQLAlchemyRuntimeAdmissionRepository",
    "SQLAlchemyRuntimeAuditRepository",
    "SQLAlchemyRuntimeIdempotencyRepository",
    "SQLAlchemyRuntimeOutboxRepository",
    "SQLAlchemyRuntimePermitRepository",
)
