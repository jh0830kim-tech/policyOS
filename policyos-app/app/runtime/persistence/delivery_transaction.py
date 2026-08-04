"""Atomic PostgreSQL implementation for initial CP8 effect enqueue."""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.runtime.persistence.delivery_serialization import (
    deserialize_delivery_model,
    serialize_delivery_model,
)
from app.runtime.persistence.errors import (
    RuntimePersistenceTransactionError,
)
from app.runtime.persistence.models import (
    RuntimeEffect,
    RuntimeEffectLifecycleHead,
    RuntimeEffectLifecycleRevision,
    RuntimeTransactionRecord,
)
from app.runtime.persistence.transaction import _persist_runtime_atomic_write_set
from app.runtime.ports import (
    RuntimeClockPort,
    RuntimeEffectAtomicCommitResult,
    RuntimeEffectAtomicWriteSet,
    RuntimeEffectCommitDisposition,
    RuntimeEffectLifecycleReceipt,
    RuntimeEffectLifecycleReceiptFact,
    RuntimeEffectReceipt,
    RuntimeEffectReceiptFact,
    RuntimeInitialEffectEnqueue,
    RuntimePortEffectConflictError,
    RuntimeTransactionReceipt,
    validate_runtime_clock_reading,
    validate_runtime_effect_atomic_commit_result,
    validate_runtime_effect_atomic_write_set,
    validate_runtime_initial_effect_replay,
    validate_runtime_transaction_receipt,
)

_EFFECT_CONSTRAINTS = {
    "uq_runtime_effect_scope_id",
    "uq_runtime_effect_scope_key",
    "runtime_effects_pkey",
}


def _transaction_receipt(row: RuntimeTransactionRecord) -> RuntimeTransactionReceipt:
    return RuntimeTransactionReceipt(
        runtime_transaction_receipt_id=row.runtime_transaction_receipt_id,
        runtime_transaction_id=row.runtime_transaction_id,
        state_record_revision=row.state_record_revision,
        audit_trail_revision=row.audit_trail_revision,
        idempotency_reservation_id=row.idempotency_reservation_id,
        outbox_enqueue_record_id=row.outbox_enqueue_record_id,
        persisted_record_receipt_ids=tuple(UUID(item) for item in row.persisted_record_receipt_ids),
        transaction_digest_reference=row.transaction_digest_reference,
        clock_reference=row.clock_reference,
        committed_at=row.committed_at,
    )


class SQLAlchemyRuntimeEffectAtomicTransaction:
    def __init__(self, session: AsyncSession, clock: RuntimeClockPort) -> None:
        self._session = session
        self._clock = clock

    async def _replay(
        self, write_set: RuntimeEffectAtomicWriteSet
    ) -> RuntimeEffectAtomicCommitResult | None:
        identity = write_set.initial_effect_enqueue.effect_identity
        rows = (
            (
                await self._session.execute(
                    select(RuntimeEffect).where(
                        RuntimeEffect.tenant_id == identity.tenant_id,
                        RuntimeEffect.organization_id == identity.organization_id,
                        or_(
                            RuntimeEffect.runtime_effect_id == identity.runtime_effect_id,
                            RuntimeEffect.effect_idempotency_key == identity.effect_idempotency_key,
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )
        if not rows:
            return None
        if len(rows) != 1:
            raise RuntimePortEffectConflictError(
                "effect identifier and idempotency key resolve differently"
            )
        effect = rows[0]
        initial = deserialize_delivery_model(
            RuntimeInitialEffectEnqueue, effect.initial_effect_enqueue_payload
        )
        validate_runtime_initial_effect_replay(write_set.initial_effect_enqueue, initial)
        if (
            effect.runtime_effect_id != identity.runtime_effect_id
            or effect.effect_idempotency_key != identity.effect_idempotency_key
        ):
            raise RuntimePortEffectConflictError("effect scoped identity conflicts")
        transaction = (
            await self._session.execute(
                select(RuntimeTransactionRecord).where(
                    RuntimeTransactionRecord.tenant_id == identity.tenant_id,
                    RuntimeTransactionRecord.organization_id == identity.organization_id,
                    RuntimeTransactionRecord.runtime_transaction_id
                    == identity.originating_transaction_id,
                )
            )
        ).scalar_one()
        revision = (
            await self._session.execute(
                select(RuntimeEffectLifecycleRevision).where(
                    RuntimeEffectLifecycleRevision.tenant_id == identity.tenant_id,
                    RuntimeEffectLifecycleRevision.organization_id == identity.organization_id,
                    RuntimeEffectLifecycleRevision.runtime_effect_id == identity.runtime_effect_id,
                    RuntimeEffectLifecycleRevision.lifecycle_revision == 1,
                )
            )
        ).scalar_one()
        transaction_receipt = validate_runtime_transaction_receipt(
            write_set.base_write_set, _transaction_receipt(transaction)
        )
        effect_fact = deserialize_delivery_model(
            RuntimeEffectReceiptFact, effect.effect_receipt_fact_payload
        )
        lifecycle_fact = deserialize_delivery_model(
            RuntimeEffectLifecycleReceiptFact, revision.receipt_fact_payload
        )
        result = RuntimeEffectAtomicCommitResult(
            disposition=RuntimeEffectCommitDisposition.EXACT_REPLAY,
            transaction_receipt=transaction_receipt,
            effect_receipt=RuntimeEffectReceipt(
                receipt_fact=effect_fact, stored_at=effect.stored_at
            ),
            lifecycle_receipt=RuntimeEffectLifecycleReceipt(
                receipt_fact=lifecycle_fact, stored_at=revision.stored_at
            ),
        )
        return validate_runtime_effect_atomic_commit_result(write_set, result)

    async def commit_effect(
        self, write_set: RuntimeEffectAtomicWriteSet
    ) -> RuntimeEffectAtomicCommitResult:
        validate_runtime_effect_atomic_write_set(write_set)
        if self._session.in_transaction():
            raise RuntimePersistenceTransactionError(
                "effect transaction requires a fresh caller-owned AsyncSession"
            )
        async with self._session.begin():
            replay = await self._replay(write_set)
        if replay is not None:
            return replay
        reading = validate_runtime_clock_reading(
            self._clock.read(),
            expected_clock_reference=write_set.base_write_set.commit_facts.clock_reference,
        )
        if reading.observed_at < write_set.base_write_set.requested_at:
            raise RuntimePersistenceTransactionError(
                "injected commit clock predates the atomic effect request"
            )
        initial = write_set.initial_effect_enqueue
        identity = initial.effect_identity
        lifecycle = initial.initial_lifecycle_record
        try:
            async with self._session.begin():
                transaction_receipt = await _persist_runtime_atomic_write_set(
                    self._session,
                    write_set.base_write_set,
                    stored_at=reading.observed_at,
                )
                self._session.add(
                    RuntimeEffect(
                        runtime_effect_receipt_id=(
                            initial.effect_receipt_fact.runtime_effect_receipt_id
                        ),
                        runtime_effect_id=identity.runtime_effect_id,
                        tenant_id=identity.tenant_id,
                        organization_id=identity.organization_id,
                        classification=identity.classification.value,
                        effect_idempotency_key=identity.effect_idempotency_key,
                        effect_fingerprint_digest_reference=(
                            identity.effect_fingerprint_digest_reference
                        ),
                        runtime_effect_delivery_envelope_id=(
                            initial.delivery_envelope.runtime_effect_delivery_envelope_id
                        ),
                        envelope_digest_reference=(
                            initial.delivery_envelope.envelope_digest_reference
                        ),
                        originating_outbox_enqueue_record_id=(
                            identity.originating_outbox_enqueue_record_id
                        ),
                        originating_transaction_id=identity.originating_transaction_id,
                        originating_transaction_receipt_id=(
                            identity.originating_transaction_receipt_id
                        ),
                        initial_effect_enqueue_payload=serialize_delivery_model(initial),
                        effect_receipt_fact_payload=serialize_delivery_model(
                            initial.effect_receipt_fact
                        ),
                        stored_at=reading.observed_at,
                    )
                )
                self._session.add(
                    RuntimeEffectLifecycleRevision(
                        runtime_effect_lifecycle_receipt_id=(
                            initial.lifecycle_receipt_fact.runtime_effect_lifecycle_receipt_id
                        ),
                        tenant_id=identity.tenant_id,
                        organization_id=identity.organization_id,
                        classification=identity.classification.value,
                        runtime_effect_id=identity.runtime_effect_id,
                        runtime_effect_lifecycle_record_id=(
                            lifecycle.runtime_effect_lifecycle_record_id
                        ),
                        lifecycle_revision=1,
                        lifecycle_status=lifecycle.status.value,
                        lifecycle_digest_reference=lifecycle.lifecycle_digest_reference,
                        source_transaction_id=identity.originating_transaction_id,
                        lifecycle_append_request_id=None,
                        claim_request_id=None,
                        lifecycle_record_payload=serialize_delivery_model(lifecycle),
                        write_request_payload=serialize_delivery_model(initial),
                        receipt_fact_payload=serialize_delivery_model(
                            initial.lifecycle_receipt_fact
                        ),
                        requested_at=write_set.base_write_set.requested_at,
                        stored_at=reading.observed_at,
                    )
                )
                self._session.add(
                    RuntimeEffectLifecycleHead(
                        tenant_id=identity.tenant_id,
                        organization_id=identity.organization_id,
                        runtime_effect_id=identity.runtime_effect_id,
                        classification=identity.classification.value,
                        current_lifecycle_revision=1,
                        current_lifecycle_record_id=(lifecycle.runtime_effect_lifecycle_record_id),
                        current_status=lifecycle.status.value,
                        current_lifecycle_digest_reference=(lifecycle.lifecycle_digest_reference),
                        current_lifecycle_payload=serialize_delivery_model(lifecycle),
                        next_eligible_at=lifecycle.recorded_at,
                        latest_attempt_count=0,
                        updated_at=reading.observed_at,
                    )
                )
                await self._session.flush()
        except IntegrityError as exc:
            constraint = getattr(getattr(exc, "orig", None), "constraint_name", None)
            if constraint is None:
                constraint = getattr(
                    getattr(getattr(exc, "orig", None), "diag", None), "constraint_name", None
                )
            if constraint not in _EFFECT_CONSTRAINTS:
                raise RuntimePersistenceTransactionError(
                    "runtime atomic effect transaction conflicted"
                ) from exc
            replay = await self._replay(write_set)
            if replay is None:
                raise RuntimePortEffectConflictError(
                    "effect uniqueness conflicted without scoped original"
                ) from exc
            return replay
        except SQLAlchemyError as exc:
            raise RuntimePersistenceTransactionError(
                "runtime atomic effect transaction failed"
            ) from exc
        result = RuntimeEffectAtomicCommitResult(
            disposition=RuntimeEffectCommitDisposition.COMMITTED,
            transaction_receipt=transaction_receipt,
            effect_receipt=RuntimeEffectReceipt(
                receipt_fact=initial.effect_receipt_fact,
                stored_at=reading.observed_at,
            ),
            lifecycle_receipt=RuntimeEffectLifecycleReceipt(
                receipt_fact=initial.lifecycle_receipt_fact,
                stored_at=reading.observed_at,
            ),
        )
        return validate_runtime_effect_atomic_commit_result(write_set, result)


__all__ = ("SQLAlchemyRuntimeEffectAtomicTransaction",)
