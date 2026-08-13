"""PostgreSQL exact persistence for ADR-103 Runtime rate admission."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.runtime_rate_admission import (
    RuntimeRateAdmissionDecisionRecord,
    RuntimeRatePolicyRevisionRecord,
    RuntimeRatePolicyRevocationRecord,
    RuntimeRateWindowCounterRecord,
)
from app.runtime.persistence.errors import (
    RuntimePersistenceError,
    RuntimeRatePermissionDeniedError,
    RuntimeRatePersistenceConflictError,
    RuntimeRatePolicyUnavailableError,
    RuntimeRateTransactionError,
)
from app.runtime.persistence.rate_admission_serialization import (
    deserialize_rate_admission_decision,
    deserialize_rate_policy_provision,
    deserialize_rate_policy_revocation,
    serialize_rate_admission_decision,
    serialize_rate_policy_provision,
    serialize_rate_policy_revocation,
)
from app.runtime.ports import (
    RuntimeRateAdmissionDecision,
    RuntimeRateAdmissionDecisionRequest,
    RuntimeRateAdmissionDisposition,
    RuntimeRateAdmissionPersistenceResult,
    RuntimeRatePersistenceDisposition,
    RuntimeRatePolicyLocator,
    RuntimeRatePolicyProvisionCommand,
    RuntimeRatePolicyProvisionResult,
    RuntimeRatePolicyRevision,
    RuntimeRatePolicyRevocationCommand,
    RuntimeRatePolicyRevocationResult,
    RuntimeRateWindowIdentity,
)

_RATE_POLICY_PERMISSION_ID = "00000000-0000-0000-0000-000000001905"
_RATE_POLICY_PERMISSION_KEY = "runtime.rate_policy.manage"
_RATE_POLICY_PERMISSION_NAME = "Runtime rate-policy management"
_RATE_POLICY_PERMISSION_DESCRIPTION = (
    "Manage governed Runtime rate-policy revisions and revocations."
)
_CLASSIFICATION_RANK = {
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "restricted": 3,
}


def _locator_values(locator: RuntimeRatePolicyLocator) -> tuple[object, ...]:
    return (
        locator.tenant_id,
        locator.organization_id,
        locator.principal_id,
        locator.operation.value,
        locator.classification.value,
        locator.policy_id,
        locator.policy_revision,
        locator.policy_reference,
    )


def _stored_locator_values(row: object) -> tuple[object, ...]:
    return (
        row.tenant_id,
        row.organization_id,
        row.principal_id,
        row.operation,
        row.classification,
        row.policy_id,
        row.policy_revision,
        row.policy_reference,
    )


def _locator_predicates(model, locator: RuntimeRatePolicyLocator) -> tuple[object, ...]:
    return (
        model.tenant_id == locator.tenant_id,
        model.organization_id == locator.organization_id,
        model.principal_id == locator.principal_id,
        model.operation == locator.operation.value,
        model.classification == locator.classification.value,
        model.policy_id == locator.policy_id,
        model.policy_revision == locator.policy_revision,
        model.policy_reference == locator.policy_reference,
    )


def _window_for(
    policy: RuntimeRatePolicyRevision, observed_at: datetime
) -> RuntimeRateWindowIdentity:
    observed = observed_at.astimezone(UTC)
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    elapsed = observed - epoch
    elapsed_microseconds = (
        elapsed.days * 86_400 + elapsed.seconds
    ) * 1_000_000 + elapsed.microseconds
    window_microseconds = policy.window_seconds * 1_000_000
    start = epoch + timedelta(
        microseconds=(elapsed_microseconds // window_microseconds) * window_microseconds
    )
    return RuntimeRateWindowIdentity(
        window_start=start,
        window_end=start + timedelta(seconds=policy.window_seconds),
    )


def _retry_after(window: RuntimeRateWindowIdentity, observed_at: datetime) -> int:
    remaining = window.window_end - observed_at
    microseconds = (
        remaining.days * 86_400 + remaining.seconds
    ) * 1_000_000 + remaining.microseconds
    return min(86_400, max(1, (microseconds + 999_999) // 1_000_000))


class SQLAlchemyRuntimeRateAdmissionRepository:
    """Store exact policy, revocation, counter, and decision facts in one root transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _require_transaction(self) -> None:
        if not self._session.in_transaction() or self._session.in_nested_transaction():
            raise RuntimeRateTransactionError(
                "rate-admission persistence requires one active root transaction"
            )

    async def _verify_management_authority(
        self,
        *,
        locator: RuntimeRatePolicyLocator,
        actor_user_id,
        actor_membership_id,
    ) -> None:
        result = await self._session.execute(
            text(
                """
                SELECT b.classification_ceiling
                FROM users AS u
                JOIN memberships AS m
                  ON m.user_id = u.id
                JOIN organizations AS o
                  ON o.id = m.organization_id
                JOIN tenant_organization_bindings AS b
                  ON b.organization_id = o.id
                JOIN membership_roles AS mr
                  ON mr.membership_id = m.id
                JOIN roles AS r
                  ON r.id = mr.role_id AND r.organization_id = o.id
                JOIN role_permissions AS rp
                  ON rp.role_id = r.id
                JOIN permissions AS p
                  ON p.id = rp.permission_id
                WHERE u.id = :actor_user_id
                  AND u.is_active
                  AND m.id = :membership_id
                  AND m.organization_id = :organization_id
                  AND m.status = 'active'
                  AND o.id = :organization_id
                  AND o.is_active
                  AND b.runtime_tenant_id = :tenant_id
                  AND b.organization_id = :organization_id
                  AND b.status = 'active'
                  AND p.id = :permission_id
                  AND p.key = :permission_key
                  AND p.name = :permission_name
                  AND p.description = :permission_description
                  AND u.xmin::text::bigint <> txid_current()
                  AND m.xmin::text::bigint <> txid_current()
                  AND o.xmin::text::bigint <> txid_current()
                  AND b.xmin::text::bigint <> txid_current()
                  AND mr.xmin::text::bigint <> txid_current()
                  AND r.xmin::text::bigint <> txid_current()
                  AND rp.xmin::text::bigint <> txid_current()
                  AND p.xmin::text::bigint <> txid_current()
                FOR UPDATE OF u, m, o, b, mr, r, rp, p
                """
            ),
            {
                "actor_user_id": actor_user_id,
                "membership_id": actor_membership_id,
                "organization_id": locator.organization_id,
                "tenant_id": locator.tenant_id,
                "permission_id": _RATE_POLICY_PERMISSION_ID,
                "permission_key": _RATE_POLICY_PERMISSION_KEY,
                "permission_name": _RATE_POLICY_PERMISSION_NAME,
                "permission_description": _RATE_POLICY_PERMISSION_DESCRIPTION,
            },
        )
        rows = result.all()
        if len(rows) != 1:
            raise RuntimeRatePermissionDeniedError("rate-policy management authority unavailable")
        if _CLASSIFICATION_RANK[locator.classification.value] > _CLASSIFICATION_RANK[rows[0][0]]:
            raise RuntimeRatePermissionDeniedError("rate-policy classification exceeds scope")

    async def _policy_row(
        self, locator: RuntimeRatePolicyLocator, *, lock: bool
    ) -> RuntimeRatePolicyRevisionRecord:
        statement = select(RuntimeRatePolicyRevisionRecord).where(
            *_locator_predicates(RuntimeRatePolicyRevisionRecord, locator)
        )
        if lock:
            statement = statement.with_for_update()
        row = (await self._session.execute(statement)).scalar_one_or_none()
        if row is None:
            raise RuntimeRatePolicyUnavailableError("exact rate policy is unavailable")
        command = deserialize_rate_policy_provision(row.provision_payload)
        if command.policy.locator != locator or _stored_locator_values(row) != _locator_values(
            locator
        ):
            raise RuntimeRatePersistenceConflictError("stored rate-policy binding differs")
        return row

    async def read_exact_policy(
        self, locator: RuntimeRatePolicyLocator
    ) -> RuntimeRatePolicyRevision:
        self._require_transaction()
        row = await self._policy_row(locator, lock=False)
        revoked = (
            await self._session.execute(
                select(RuntimeRatePolicyRevocationRecord).where(
                    *_locator_predicates(RuntimeRatePolicyRevocationRecord, locator)
                )
            )
        ).scalar_one_or_none()
        if revoked is not None:
            raise RuntimeRatePolicyUnavailableError("exact rate policy is revoked")
        return deserialize_rate_policy_provision(row.provision_payload).policy

    async def provision_policy(
        self, command: RuntimeRatePolicyProvisionCommand
    ) -> RuntimeRatePolicyProvisionResult:
        self._require_transaction()
        if command.permission_reference != f"permission:{_RATE_POLICY_PERMISSION_ID}":
            raise RuntimeRatePermissionDeniedError("rate-policy permission reference differs")
        policy = command.policy
        try:
            collisions = (
                (
                    await self._session.execute(
                        select(RuntimeRatePolicyRevisionRecord)
                        .where(
                            or_(
                                (
                                    RuntimeRatePolicyRevisionRecord.tenant_id
                                    == policy.locator.tenant_id
                                )
                                & (
                                    RuntimeRatePolicyRevisionRecord.organization_id
                                    == policy.locator.organization_id
                                )
                                & (
                                    RuntimeRatePolicyRevisionRecord.provisioning_request_id
                                    == policy.provisioning_request_id
                                ),
                                (
                                    RuntimeRatePolicyRevisionRecord.tenant_id
                                    == policy.locator.tenant_id
                                )
                                & (
                                    RuntimeRatePolicyRevisionRecord.organization_id
                                    == policy.locator.organization_id
                                )
                                & (
                                    RuntimeRatePolicyRevisionRecord.provisioning_receipt_id
                                    == policy.provisioning_receipt_id
                                ),
                                and_(
                                    *_locator_predicates(
                                        RuntimeRatePolicyRevisionRecord, policy.locator
                                    )
                                ),
                            )
                        )
                        .with_for_update()
                    )
                )
                .scalars()
                .all()
            )
            unique = {id(row): row for row in collisions}
            if unique:
                if (
                    len(unique) == 1
                    and deserialize_rate_policy_provision(
                        next(iter(unique.values())).provision_payload
                    )
                    == command
                ):
                    return RuntimeRatePolicyProvisionResult(
                        disposition=RuntimeRatePersistenceDisposition.EXACT_REPLAY,
                        policy=policy,
                    )
                raise RuntimeRatePersistenceConflictError("rate-policy provision replay differs")
            await self._verify_management_authority(
                locator=policy.locator,
                actor_user_id=policy.actor_user_id,
                actor_membership_id=policy.actor_membership_id,
            )
            self._session.add(
                RuntimeRatePolicyRevisionRecord(
                    tenant_id=policy.locator.tenant_id,
                    organization_id=policy.locator.organization_id,
                    principal_id=policy.locator.principal_id,
                    operation=policy.locator.operation.value,
                    classification=policy.locator.classification.value,
                    policy_id=policy.locator.policy_id,
                    policy_revision=policy.locator.policy_revision,
                    policy_reference=policy.locator.policy_reference,
                    admission_limit=policy.admission_limit,
                    window_seconds=policy.window_seconds,
                    effective_from=policy.effective_from,
                    valid_until=policy.valid_until,
                    provisioning_request_id=policy.provisioning_request_id,
                    provisioning_receipt_id=policy.provisioning_receipt_id,
                    actor_principal_id=policy.actor_principal_id,
                    actor_user_id=policy.actor_user_id,
                    actor_membership_id=policy.actor_membership_id,
                    reason_reference=policy.reason_reference,
                    provenance_reference=policy.provenance_reference,
                    request_digest=policy.request_digest,
                    command_version=policy.command_version,
                    permission_reference=command.permission_reference,
                    provision_payload=serialize_rate_policy_provision(command),
                    requested_at=policy.requested_at,
                    committed_at=policy.committed_at,
                )
            )
            await self._session.flush()
            return RuntimeRatePolicyProvisionResult(
                disposition=RuntimeRatePersistenceDisposition.COMMITTED,
                policy=policy,
            )
        except RuntimePersistenceError:
            raise
        except IntegrityError as exc:
            raise RuntimeRatePersistenceConflictError(
                "rate-policy relational constraint conflicted"
            ) from exc
        except SQLAlchemyError as exc:
            raise RuntimePersistenceError("rate-policy provision failed") from exc

    async def revoke_policy(
        self, command: RuntimeRatePolicyRevocationCommand
    ) -> RuntimeRatePolicyRevocationResult:
        self._require_transaction()
        try:
            collisions = (
                (
                    await self._session.execute(
                        select(RuntimeRatePolicyRevocationRecord)
                        .where(
                            or_(
                                (
                                    RuntimeRatePolicyRevocationRecord.tenant_id
                                    == command.locator.tenant_id
                                )
                                & (
                                    RuntimeRatePolicyRevocationRecord.organization_id
                                    == command.locator.organization_id
                                )
                                & (
                                    RuntimeRatePolicyRevocationRecord.revocation_request_id
                                    == command.revocation_request_id
                                ),
                                (
                                    RuntimeRatePolicyRevocationRecord.tenant_id
                                    == command.locator.tenant_id
                                )
                                & (
                                    RuntimeRatePolicyRevocationRecord.organization_id
                                    == command.locator.organization_id
                                )
                                & (
                                    RuntimeRatePolicyRevocationRecord.revocation_receipt_id
                                    == command.revocation_receipt_id
                                ),
                                and_(
                                    *_locator_predicates(
                                        RuntimeRatePolicyRevocationRecord, command.locator
                                    )
                                ),
                            )
                        )
                        .with_for_update()
                    )
                )
                .scalars()
                .all()
            )
            unique = {id(row): row for row in collisions}
            if unique:
                if (
                    len(unique) == 1
                    and deserialize_rate_policy_revocation(
                        next(iter(unique.values())).revocation_payload
                    )
                    == command
                ):
                    return RuntimeRatePolicyRevocationResult(
                        disposition=RuntimeRatePersistenceDisposition.EXACT_REPLAY,
                        revocation=command,
                    )
                raise RuntimeRatePersistenceConflictError("rate-policy revocation replay differs")
            await self._policy_row(command.locator, lock=True)
            await self._verify_management_authority(
                locator=command.locator,
                actor_user_id=command.actor_user_id,
                actor_membership_id=command.actor_membership_id,
            )
            self._session.add(
                RuntimeRatePolicyRevocationRecord(
                    tenant_id=command.locator.tenant_id,
                    organization_id=command.locator.organization_id,
                    revocation_request_id=command.revocation_request_id,
                    revocation_receipt_id=command.revocation_receipt_id,
                    principal_id=command.locator.principal_id,
                    operation=command.locator.operation.value,
                    classification=command.locator.classification.value,
                    policy_id=command.locator.policy_id,
                    policy_revision=command.locator.policy_revision,
                    policy_reference=command.locator.policy_reference,
                    actor_principal_id=command.actor_principal_id,
                    actor_user_id=command.actor_user_id,
                    actor_membership_id=command.actor_membership_id,
                    reason_reference=command.reason_reference,
                    provenance_reference=command.provenance_reference,
                    request_digest=command.request_digest,
                    revoked_at=command.revoked_at,
                    revocation_payload=serialize_rate_policy_revocation(command),
                )
            )
            await self._session.flush()
            return RuntimeRatePolicyRevocationResult(
                disposition=RuntimeRatePersistenceDisposition.COMMITTED,
                revocation=command,
            )
        except RuntimePersistenceError:
            raise
        except IntegrityError as exc:
            raise RuntimeRatePersistenceConflictError(
                "rate-policy revocation constraint conflicted"
            ) from exc
        except SQLAlchemyError as exc:
            raise RuntimePersistenceError("rate-policy revocation failed") from exc

    async def _decision_replay(
        self, request: RuntimeRateAdmissionDecisionRequest
    ) -> RuntimeRateAdmissionPersistenceResult | None:
        locator = request.policy.locator
        rows = (
            (
                await self._session.execute(
                    select(RuntimeRateAdmissionDecisionRecord)
                    .where(
                        or_(
                            RuntimeRateAdmissionDecisionRecord.decision_id == request.decision_id,
                            (RuntimeRateAdmissionDecisionRecord.tenant_id == locator.tenant_id)
                            & (
                                RuntimeRateAdmissionDecisionRecord.organization_id
                                == locator.organization_id
                            )
                            & (RuntimeRateAdmissionDecisionRecord.request_id == request.request_id),
                            (RuntimeRateAdmissionDecisionRecord.tenant_id == locator.tenant_id)
                            & (
                                RuntimeRateAdmissionDecisionRecord.organization_id
                                == locator.organization_id
                            )
                            & (
                                RuntimeRateAdmissionDecisionRecord.preparation_id
                                == request.preparation_id
                            ),
                            (RuntimeRateAdmissionDecisionRecord.tenant_id == locator.tenant_id)
                            & (
                                RuntimeRateAdmissionDecisionRecord.organization_id
                                == locator.organization_id
                            )
                            & (
                                RuntimeRateAdmissionDecisionRecord.decision_reference
                                == request.decision_reference
                            ),
                        )
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        unique = {id(row): row for row in rows}
        if not unique:
            return None
        if len(unique) != 1:
            raise RuntimeRatePersistenceConflictError("rate-admission replay identities differ")
        decision = deserialize_rate_admission_decision(next(iter(unique.values())).decision_payload)
        if decision.request != request:
            raise RuntimeRatePersistenceConflictError("rate-admission replay facts differ")
        return RuntimeRateAdmissionPersistenceResult(
            persistence_disposition=RuntimeRatePersistenceDisposition.EXACT_REPLAY,
            decision=decision,
        )

    async def admit(
        self, request: RuntimeRateAdmissionDecisionRequest
    ) -> RuntimeRateAdmissionPersistenceResult:
        self._require_transaction()
        try:
            replay = await self._decision_replay(request)
            if replay is not None:
                return replay
            policy_row = await self._policy_row(request.policy.locator, lock=True)
            persisted_policy = deserialize_rate_policy_provision(
                policy_row.provision_payload
            ).policy
            if persisted_policy != request.policy:
                raise RuntimeRatePersistenceConflictError("rate-admission policy differs")
            revoked = (
                await self._session.execute(
                    select(RuntimeRatePolicyRevocationRecord).where(
                        *_locator_predicates(
                            RuntimeRatePolicyRevocationRecord, request.policy.locator
                        )
                    )
                )
            ).scalar_one_or_none()
            if not (
                request.policy.effective_from <= request.observed_at < request.policy.valid_until
            ):
                raise RuntimeRatePolicyUnavailableError("rate policy is outside validity")
            if revoked is not None and request.observed_at >= revoked.revoked_at:
                raise RuntimeRatePolicyUnavailableError("rate policy is revoked")
            expected_window = _window_for(request.policy, request.observed_at)
            if request.window != expected_window:
                raise RuntimeRatePersistenceConflictError("rate window differs")
            locator = request.policy.locator
            lock_identity = "|".join(
                str(value)
                for value in (
                    *_locator_values(locator),
                    request.window.window_start.isoformat(),
                    request.window.window_end.isoformat(),
                )
            )
            await self._session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:identity, 0))"),
                {"identity": lock_identity},
            )
            counter = (
                await self._session.execute(
                    select(RuntimeRateWindowCounterRecord)
                    .where(
                        *_locator_predicates(RuntimeRateWindowCounterRecord, locator),
                        RuntimeRateWindowCounterRecord.window_start == request.window.window_start,
                        RuntimeRateWindowCounterRecord.window_end == request.window.window_end,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            before = 0 if counter is None else counter.admitted_count
            admitted = before < request.policy.admission_limit
            after = before + 1 if admitted else before
            decision = RuntimeRateAdmissionDecision(
                request=request,
                disposition=(
                    RuntimeRateAdmissionDisposition.ADMITTED
                    if admitted
                    else RuntimeRateAdmissionDisposition.DENIED
                ),
                retry_after_seconds=(
                    None if admitted else _retry_after(request.window, request.observed_at)
                ),
                admitted_count_before=before,
                admitted_count_after=after,
            )
            self._session.add(
                RuntimeRateAdmissionDecisionRecord(
                    decision_id=request.decision_id,
                    tenant_id=locator.tenant_id,
                    organization_id=locator.organization_id,
                    principal_id=locator.principal_id,
                    operation=locator.operation.value,
                    classification=locator.classification.value,
                    policy_id=locator.policy_id,
                    policy_revision=locator.policy_revision,
                    policy_reference=locator.policy_reference,
                    preparation_id=request.preparation_id,
                    request_id=request.request_id,
                    request_digest=request.request_digest,
                    clock_reference=request.clock_reference,
                    observed_at=request.observed_at,
                    window_start=request.window.window_start,
                    window_end=request.window.window_end,
                    disposition=decision.disposition.value,
                    retry_after_seconds=decision.retry_after_seconds,
                    admitted_count_before=before,
                    admitted_count_after=after,
                    decision_reference=request.decision_reference,
                    decision_digest=request.decision_digest,
                    evaluated_at=request.evaluated_at,
                    committed_at=request.committed_at,
                    provenance_reference=request.provenance_reference,
                    decision_payload=serialize_rate_admission_decision(decision),
                )
            )
            await self._session.flush()
            if admitted and counter is None:
                self._session.add(
                    RuntimeRateWindowCounterRecord(
                        tenant_id=locator.tenant_id,
                        organization_id=locator.organization_id,
                        principal_id=locator.principal_id,
                        operation=locator.operation.value,
                        classification=locator.classification.value,
                        policy_id=locator.policy_id,
                        policy_revision=locator.policy_revision,
                        policy_reference=locator.policy_reference,
                        window_start=request.window.window_start,
                        window_end=request.window.window_end,
                        admitted_count=after,
                        last_decision_id=request.decision_id,
                        last_request_id=request.request_id,
                        last_preparation_id=request.preparation_id,
                    )
                )
                await self._session.flush()
            elif admitted:
                result = await self._session.execute(
                    update(RuntimeRateWindowCounterRecord)
                    .where(
                        *_locator_predicates(RuntimeRateWindowCounterRecord, locator),
                        RuntimeRateWindowCounterRecord.window_start == request.window.window_start,
                        RuntimeRateWindowCounterRecord.window_end == request.window.window_end,
                        RuntimeRateWindowCounterRecord.admitted_count == before,
                    )
                    .values(
                        admitted_count=after,
                        last_decision_id=request.decision_id,
                        last_request_id=request.request_id,
                        last_preparation_id=request.preparation_id,
                    )
                )
                if result.rowcount != 1:
                    raise RuntimeRatePersistenceConflictError("rate counter changed concurrently")
            return RuntimeRateAdmissionPersistenceResult(
                persistence_disposition=RuntimeRatePersistenceDisposition.COMMITTED,
                decision=decision,
            )
        except RuntimePersistenceError:
            raise
        except IntegrityError as exc:
            raise RuntimeRatePersistenceConflictError(
                "rate-admission relational constraint conflicted"
            ) from exc
        except SQLAlchemyError as exc:
            raise RuntimePersistenceError("rate-admission persistence failed") from exc


__all__ = ("SQLAlchemyRuntimeRateAdmissionRepository",)
