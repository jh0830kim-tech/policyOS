"""PostgreSQL repositories for CP8 effect delivery lifecycle persistence."""

from sqlalchemy import and_, case, null, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.runtime.persistence.delivery_serialization import (
    deserialize_delivery_model,
    serialize_delivery_model,
)
from app.runtime.persistence.errors import RuntimePersistenceConflictError, RuntimePersistenceError
from app.runtime.persistence.models import (
    RuntimeEffect,
    RuntimeEffectLifecycleHead,
    RuntimeEffectLifecycleRevision,
    RuntimeEffectReconciliationObservationRecord,
)
from app.runtime.ports import (
    RuntimeEffectClaim,
    RuntimeEffectClaimRequest,
    RuntimeEffectDueCandidate,
    RuntimeEffectDueReason,
    RuntimeEffectDueSelectionRequest,
    RuntimeEffectLifecycleAppendRequest,
    RuntimeEffectLifecycleCommitDisposition,
    RuntimeEffectLifecycleCommitResult,
    RuntimeEffectLifecycleReceipt,
    RuntimeEffectLifecycleReceiptFact,
    RuntimeEffectLifecycleRecord,
    RuntimeEffectLifecycleStatus,
    RuntimeEffectRetryDecision,
    RuntimeInitialEffectEnqueue,
    RuntimePortClaimError,
    RuntimePortEffectConflictError,
    validate_runtime_effect_claim_request,
    validate_runtime_effect_due_candidates,
    validate_runtime_effect_lifecycle_append_request,
    validate_runtime_effect_lifecycle_commit_result,
    validate_runtime_effect_lifecycle_replay,
)

_TERMINAL = {RuntimeEffectLifecycleStatus.DELIVERED, RuntimeEffectLifecycleStatus.DEAD_LETTERED}


def _scope(model, identity):
    return (
        model.tenant_id == identity.tenant_id,
        model.organization_id == identity.organization_id,
        model.runtime_effect_id == identity.runtime_effect_id,
        model.classification == identity.classification.value,
    )


def _receipt(row):
    fact = deserialize_delivery_model(RuntimeEffectLifecycleReceiptFact, row.receipt_fact_payload)
    return RuntimeEffectLifecycleReceipt(receipt_fact=fact, stored_at=row.stored_at)


async def _existing(session, request_id, *, claim):
    column = (
        RuntimeEffectLifecycleRevision.claim_request_id
        if claim
        else RuntimeEffectLifecycleRevision.lifecycle_append_request_id
    )
    return (
        await session.execute(select(RuntimeEffectLifecycleRevision).where(column == request_id))
    ).scalar_one_or_none()


def _exact_replay(existing, request, *, claim):
    stored = deserialize_delivery_model(
        RuntimeEffectClaimRequest if claim else RuntimeEffectLifecycleAppendRequest,
        existing.write_request_payload,
    )
    if claim:
        if stored != request:
            raise RuntimePortEffectConflictError("claim replay immutable facts differ")
    else:
        validate_runtime_effect_lifecycle_replay(stored, request)
    return RuntimeEffectLifecycleCommitResult(
        disposition=RuntimeEffectLifecycleCommitDisposition.EXACT_REPLAY,
        receipt=_receipt(existing),
    )


def _revision(request, *, stored_at):
    claim_request = isinstance(request, RuntimeEffectClaimRequest)
    append = None if claim_request else request.append
    record = request.claimed_lifecycle_record if claim_request else append.lifecycle_record
    identity = request.effect_identity if claim_request else append.effect_identity
    claim = request.claim if claim_request else append.claim
    not_invoked = None if claim_request else append.definitely_not_invoked
    claim_id = (
        claim.runtime_effect_claim_id
        if claim is not None
        else (
            not_invoked.runtime_effect_claim_id
            if not_invoked is not None
            else record.runtime_effect_claim_id
        )
    )
    attempt_id = (
        append.attempt.runtime_effect_delivery_attempt_id
        if not claim_request and append.attempt is not None
        else (
            not_invoked.runtime_effect_delivery_attempt_id
            if not_invoked is not None
            else record.runtime_effect_delivery_attempt_id
        )
    )
    lease_id = (
        claim.lease_id
        if claim is not None
        else (not_invoked.lease_id if not_invoked is not None else None)
    )
    return RuntimeEffectLifecycleRevision(
        runtime_effect_lifecycle_receipt_id=request.receipt_fact.runtime_effect_lifecycle_receipt_id
        if claim_request
        else append.receipt_fact.runtime_effect_lifecycle_receipt_id,
        tenant_id=identity.tenant_id,
        organization_id=identity.organization_id,
        classification=identity.classification.value,
        runtime_effect_id=identity.runtime_effect_id,
        runtime_effect_lifecycle_record_id=record.runtime_effect_lifecycle_record_id,
        lifecycle_revision=record.lifecycle_revision,
        lifecycle_status=record.status.value,
        lifecycle_digest_reference=record.lifecycle_digest_reference,
        source_transaction_id=None,
        lifecycle_append_request_id=None
        if claim_request
        else request.runtime_effect_lifecycle_append_request_id,
        claim_request_id=request.runtime_effect_claim_request_id if claim_request else None,
        runtime_effect_claim_id=claim_id,
        lease_id=lease_id,
        runtime_effect_delivery_attempt_id=attempt_id,
        runtime_effect_delivery_result_id=record.runtime_effect_delivery_result_id,
        runtime_effect_retry_decision_id=record.runtime_effect_retry_decision_id,
        runtime_effect_dead_letter_record_id=record.runtime_effect_dead_letter_record_id,
        runtime_effect_definitely_not_invoked_id=None
        if not_invoked is None
        else not_invoked.runtime_effect_definitely_not_invoked_id,
        runtime_effect_reconciliation_observation_id=record.runtime_effect_reconciliation_observation_id,
        lifecycle_record_payload=serialize_delivery_model(record),
        write_request_payload=serialize_delivery_model(request),
        claim_payload=null() if claim is None else serialize_delivery_model(claim),
        attempt_payload=null()
        if claim_request or append.attempt is None
        else serialize_delivery_model(append.attempt),
        result_payload=null()
        if claim_request or append.result is None
        else serialize_delivery_model(append.result),
        definitely_not_invoked_payload=null()
        if not_invoked is None
        else serialize_delivery_model(not_invoked),
        retry_decision_payload=null()
        if claim_request or append.retry_decision is None
        else serialize_delivery_model(append.retry_decision),
        dead_letter_payload=null()
        if claim_request or append.dead_letter is None
        else serialize_delivery_model(append.dead_letter),
        receipt_fact_payload=serialize_delivery_model(
            request.receipt_fact if claim_request else append.receipt_fact
        ),
        requested_at=request.requested_at,
        stored_at=stored_at,
    )


class SQLAlchemyRuntimeEffectDueRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def select_due(
        self, request: RuntimeEffectDueSelectionRequest
    ) -> tuple[RuntimeEffectDueCandidate, ...]:
        effective = case(
            (
                RuntimeEffectLifecycleHead.current_status
                == RuntimeEffectLifecycleStatus.CLAIMED.value,
                RuntimeEffectLifecycleHead.claim_expires_at,
            ),
            else_=RuntimeEffectLifecycleHead.next_eligible_at,
        )
        rows = (
            await self._session.execute(
                select(RuntimeEffect, RuntimeEffectLifecycleHead)
                .join(
                    RuntimeEffectLifecycleHead,
                    and_(
                        RuntimeEffect.tenant_id == RuntimeEffectLifecycleHead.tenant_id,
                        RuntimeEffect.organization_id == RuntimeEffectLifecycleHead.organization_id,
                        RuntimeEffect.runtime_effect_id
                        == RuntimeEffectLifecycleHead.runtime_effect_id,
                    ),
                )
                .where(
                    RuntimeEffect.tenant_id == request.tenant_id,
                    RuntimeEffect.organization_id == request.organization_id,
                    RuntimeEffect.classification == request.classification.value,
                    or_(
                        and_(
                            RuntimeEffectLifecycleHead.current_status.in_(
                                (
                                    RuntimeEffectLifecycleStatus.ENQUEUED.value,
                                    RuntimeEffectLifecycleStatus.RETRY_SCHEDULED.value,
                                )
                            ),
                            RuntimeEffectLifecycleHead.next_eligible_at <= request.observed_at,
                        ),
                        and_(
                            RuntimeEffectLifecycleHead.current_status
                            == RuntimeEffectLifecycleStatus.CLAIMED.value,
                            RuntimeEffectLifecycleHead.claim_expires_at <= request.observed_at,
                        ),
                    ),
                )
                .order_by(effective, RuntimeEffect.runtime_effect_id)
                .limit(request.maximum_candidate_count)
            )
        ).all()
        candidates = []
        for effect, head in rows:
            initial = deserialize_delivery_model(
                RuntimeInitialEffectEnqueue, effect.initial_effect_enqueue_payload
            )
            lifecycle = deserialize_delivery_model(
                RuntimeEffectLifecycleRecord, head.current_lifecycle_payload
            )
            claim = (
                None
                if head.active_claim_payload is None
                else deserialize_delivery_model(RuntimeEffectClaim, head.active_claim_payload)
            )
            retry = (
                None
                if head.current_retry_decision_payload is None
                else deserialize_delivery_model(
                    RuntimeEffectRetryDecision, head.current_retry_decision_payload
                )
            )
            reason = (
                RuntimeEffectDueReason.CLAIM_EXPIRED
                if lifecycle.status is RuntimeEffectLifecycleStatus.CLAIMED
                else (
                    RuntimeEffectDueReason.RETRY_ELIGIBLE
                    if lifecycle.status is RuntimeEffectLifecycleStatus.RETRY_SCHEDULED
                    else RuntimeEffectDueReason.INITIAL_ENQUEUE
                )
            )
            candidates.append(
                RuntimeEffectDueCandidate(
                    effect_identity=initial.effect_identity,
                    delivery_envelope=initial.delivery_envelope,
                    current_lifecycle_record=lifecycle,
                    previous_claim=claim,
                    retry_decision=retry,
                    due_reason=reason,
                    eligible_at=head.claim_expires_at
                    if reason is RuntimeEffectDueReason.CLAIM_EXPIRED
                    else head.next_eligible_at,
                )
            )
        return validate_runtime_effect_due_candidates(request, tuple(candidates))


class SQLAlchemyRuntimeEffectLifecycleTransaction:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(
        self, request: RuntimeEffectLifecycleAppendRequest
    ) -> RuntimeEffectLifecycleCommitResult:
        validate_runtime_effect_lifecycle_append_request(request)
        return await self._commit(request, claim=False)

    async def claim(self, request: RuntimeEffectClaimRequest) -> RuntimeEffectLifecycleCommitResult:
        validate_runtime_effect_claim_request(request)
        return await self._commit(request, claim=True)

    async def _commit(self, request, *, claim):
        request_id = (
            request.runtime_effect_claim_request_id
            if claim
            else request.runtime_effect_lifecycle_append_request_id
        )
        async with self._session.begin():
            existing = await _existing(self._session, request_id, claim=claim)
        if existing is not None:
            return _exact_replay(existing, request, claim=claim)
        identity = request.effect_identity if claim else request.append.effect_identity
        previous = (
            request.previous_lifecycle_record if claim else request.append.previous_lifecycle_record
        )
        current = request.claimed_lifecycle_record if claim else request.append.lifecycle_record
        try:
            async with self._session.begin():
                head = (
                    await self._session.execute(
                        select(RuntimeEffectLifecycleHead)
                        .where(*_scope(RuntimeEffectLifecycleHead, identity))
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                existing = await _existing(self._session, request_id, claim=claim)
                if existing is not None:
                    return _exact_replay(existing, request, claim=claim)
                if head is None:
                    raise RuntimePersistenceConflictError(
                        "effect lifecycle optimistic revision conflicted"
                    )
                if head.current_status in {item.value for item in _TERMINAL}:
                    raise RuntimePortEffectConflictError("terminal effect cannot advance")
                if (
                    head.current_lifecycle_revision != previous.lifecycle_revision
                    or head.current_lifecycle_record_id
                    != previous.runtime_effect_lifecycle_record_id
                    or head.current_lifecycle_digest_reference
                    != previous.lifecycle_digest_reference
                ):
                    raise RuntimePersistenceConflictError(
                        "effect lifecycle optimistic revision conflicted"
                    )
                if claim and head.current_status == RuntimeEffectLifecycleStatus.DELIVERING.value:
                    raise RuntimePortClaimError("delivering effect cannot be reclaimed")
                if (
                    claim
                    and head.active_claim_id is not None
                    and head.claim_expires_at > request.observed_at
                ):
                    raise RuntimePortClaimError("unexpired claim cannot be replaced")
                if (
                    claim
                    and head.active_claim_id is not None
                    and (
                        head.active_claim_id == request.claim.runtime_effect_claim_id
                        or head.active_lease_id == request.claim.lease_id
                    )
                ):
                    raise RuntimePortClaimError("expired reclaim requires distinct claim and lease")
                row = _revision(request, stored_at=request.requested_at)
                self._session.add(row)
                append = None if claim else request.append
                observation = None if claim else append.reconciliation_observation
                if observation is not None:
                    self._session.add(
                        RuntimeEffectReconciliationObservationRecord(
                            runtime_effect_reconciliation_observation_id=observation.runtime_effect_reconciliation_observation_id,
                            runtime_effect_reconciliation_request_id=observation.runtime_effect_reconciliation_request_id,
                            runtime_effect_id=observation.runtime_effect_id,
                            tenant_id=observation.tenant_id,
                            organization_id=observation.organization_id,
                            classification=observation.classification.value,
                            destination_reference=observation.destination_reference,
                            outcome=observation.outcome.value,
                            observation_payload=serialize_delivery_model(observation),
                            observed_at=observation.observed_at,
                            stored_at=request.requested_at,
                        )
                    )
                new_claim = request.claim if claim else append.claim
                retry = None if claim else append.retry_decision
                head.current_lifecycle_revision = current.lifecycle_revision
                head.current_lifecycle_record_id = current.runtime_effect_lifecycle_record_id
                head.current_status = current.status.value
                head.current_lifecycle_digest_reference = current.lifecycle_digest_reference
                head.current_lifecycle_payload = serialize_delivery_model(current)
                head.active_claim_id = (
                    None if new_claim is None else new_claim.runtime_effect_claim_id
                )
                head.active_lease_id = None if new_claim is None else new_claim.lease_id
                head.claim_expires_at = None if new_claim is None else new_claim.expires_at
                head.active_claim_payload = (
                    null() if new_claim is None else serialize_delivery_model(new_claim)
                )
                head.current_retry_decision_payload = (
                    null() if retry is None else serialize_delivery_model(retry)
                )
                head.next_eligible_at = (
                    current.recorded_at
                    if current.status is RuntimeEffectLifecycleStatus.ENQUEUED
                    else (None if retry is None else retry.eligible_at)
                )
                head.latest_attempt_count = max(
                    head.latest_attempt_count,
                    0 if claim or append.attempt is None else append.attempt.attempt_number,
                )
                head.updated_at = request.requested_at
                await self._session.flush()
        except IntegrityError as exc:
            raise RuntimePersistenceConflictError("effect lifecycle uniqueness conflicted") from exc
        except SQLAlchemyError as exc:
            raise RuntimePersistenceError("effect lifecycle storage failed") from exc
        result = RuntimeEffectLifecycleCommitResult(
            disposition=RuntimeEffectLifecycleCommitDisposition.APPENDED,
            receipt=RuntimeEffectLifecycleReceipt(
                receipt_fact=request.receipt_fact if claim else request.append.receipt_fact,
                stored_at=request.requested_at,
            ),
        )
        return validate_runtime_effect_lifecycle_commit_result(request, result)


__all__ = ("SQLAlchemyRuntimeEffectDueRepository", "SQLAlchemyRuntimeEffectLifecycleTransaction")
