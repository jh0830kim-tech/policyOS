"""Atomic SQLAlchemy transaction implementation for governed runtime facts."""

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.runtime.persistence.errors import (
    RuntimePersistenceConflictError,
    RuntimePersistenceTransactionError,
)
from app.runtime.persistence.models import RuntimeTransactionRecord
from app.runtime.persistence.repositories import persist_runtime_revision
from app.runtime.ports import (
    RuntimeAtomicWriteSet,
    RuntimeClockPort,
    RuntimeTransactionReceipt,
    RuntimeTransactionRecordType,
    validate_runtime_atomic_write_set,
    validate_runtime_clock_reading,
    validate_runtime_transaction_receipt,
)


class SQLAlchemyRuntimeTransaction:
    """Commit exact caller-supplied state, audit, idempotency, and outbox facts."""

    def __init__(self, session: AsyncSession, clock: RuntimeClockPort) -> None:
        self._session = session
        self._clock = clock

    async def commit(self, write_set: RuntimeAtomicWriteSet) -> RuntimeTransactionReceipt:
        validate_runtime_atomic_write_set(write_set)
        if self._session.in_transaction():
            raise RuntimePersistenceTransactionError(
                "runtime transaction requires a fresh caller-owned AsyncSession"
            )
        reading = validate_runtime_clock_reading(
            self._clock.read(),
            expected_clock_reference=write_set.commit_facts.clock_reference,
        )
        if reading.observed_at < write_set.requested_at:
            raise RuntimePersistenceTransactionError(
                "injected commit clock predates the atomic write request"
            )
        receipt_facts = {
            item.record_type: item for item in write_set.commit_facts.record_receipts
        }
        records = (
            (
                RuntimeTransactionRecordType.EXECUTION_STATE,
                write_set.state_record,
                write_set.expected_state_revision,
                write_set.state_record.current_revision,
            ),
            (
                RuntimeTransactionRecordType.AUDIT_TRAIL,
                write_set.audit_trail,
                write_set.expected_audit_revision,
                write_set.audit_trail.trail_revision,
            ),
            (
                RuntimeTransactionRecordType.IDEMPOTENCY_RESERVATION,
                write_set.idempotency_reservation,
                None,
                1,
            ),
        )
        if write_set.outbox_enqueue_record is not None:
            records = (
                *records,
                (
                    RuntimeTransactionRecordType.OUTBOX_ENQUEUE,
                    write_set.outbox_enqueue_record,
                    None,
                    write_set.outbox_enqueue_record.outbox_revision,
                ),
            )

        try:
            async with self._session.begin():
                for record_type, record, expected_revision, resulting_revision in records:
                    fact = receipt_facts[record_type]
                    await persist_runtime_revision(
                        self._session,
                        record,
                        receipt_id=fact.runtime_repository_write_receipt_id,
                        write_request_id=None,
                        transaction_id=write_set.runtime_transaction_id,
                        expected_revision=expected_revision,
                        resulting_revision=resulting_revision,
                        digest_reference=fact.record_digest_reference,
                        requested_at=write_set.requested_at,
                        stored_at=reading.observed_at,
                    )
                scope = write_set.idempotency_reservation.scope
                outbox_id = (
                    write_set.outbox_enqueue_record.runtime_outbox_enqueue_record_id
                    if write_set.outbox_enqueue_record is not None
                    else None
                )
                persisted_ids = tuple(
                    item.runtime_repository_write_receipt_id
                    for item in write_set.commit_facts.record_receipts
                )
                self._session.add(
                    RuntimeTransactionRecord(
                        runtime_transaction_receipt_id=(
                            write_set.commit_facts.runtime_transaction_receipt_id
                        ),
                        runtime_transaction_id=write_set.runtime_transaction_id,
                        tenant_id=scope.tenant_id,
                        organization_id=scope.organization_id,
                        classification=scope.classification.value,
                        state_record_revision=write_set.state_record.current_revision,
                        audit_trail_revision=write_set.audit_trail.trail_revision,
                        idempotency_reservation_id=(
                            write_set.idempotency_reservation.runtime_idempotency_reservation_id
                        ),
                        outbox_enqueue_record_id=outbox_id,
                        persisted_record_receipt_ids=[str(item) for item in persisted_ids],
                        transaction_digest_reference=(
                            write_set.commit_facts.transaction_digest_reference
                        ),
                        clock_reference=write_set.commit_facts.clock_reference,
                        requested_at=write_set.requested_at,
                        committed_at=reading.observed_at,
                    )
                )
                await self._session.flush()
        except RuntimePersistenceConflictError:
            raise
        except IntegrityError as exc:
            raise RuntimePersistenceConflictError(
                "runtime transaction uniqueness constraint conflicted"
            ) from exc
        except SQLAlchemyError as exc:
            raise RuntimePersistenceTransactionError(
                "runtime database transaction failed"
            ) from exc

        receipt = RuntimeTransactionReceipt(
            runtime_transaction_receipt_id=(
                write_set.commit_facts.runtime_transaction_receipt_id
            ),
            runtime_transaction_id=write_set.runtime_transaction_id,
            state_record_revision=write_set.state_record.current_revision,
            audit_trail_revision=write_set.audit_trail.trail_revision,
            idempotency_reservation_id=(
                write_set.idempotency_reservation.runtime_idempotency_reservation_id
            ),
            outbox_enqueue_record_id=(
                write_set.outbox_enqueue_record.runtime_outbox_enqueue_record_id
                if write_set.outbox_enqueue_record is not None
                else None
            ),
            persisted_record_receipt_ids=tuple(
                item.runtime_repository_write_receipt_id
                for item in write_set.commit_facts.record_receipts
            ),
            transaction_digest_reference=(
                write_set.commit_facts.transaction_digest_reference
            ),
            clock_reference=write_set.commit_facts.clock_reference,
            committed_at=reading.observed_at,
        )
        return validate_runtime_transaction_receipt(write_set, receipt)


__all__ = ("SQLAlchemyRuntimeTransaction",)
