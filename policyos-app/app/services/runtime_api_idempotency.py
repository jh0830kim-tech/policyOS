"""PostgreSQL transaction-bound CP9 transport idempotency persistence."""

import hashlib

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.runtime_api_idempotency import RuntimeApiIdempotencyReceiptRecord
from app.services.runtime_api_contracts import (
    RuntimeApiCommandIdentity,
    RuntimeApiIdempotencyCommitFacts,
    RuntimeApiIdempotencyCommitResult,
    RuntimeApiIdempotencyDisposition,
    RuntimeApiIdempotencyReceipt,
    RuntimeApiOperation,
    RuntimeApiPublicStatus,
    RuntimeApiSafeResult,
    RuntimeApiStatusProjection,
)
from app.services.runtime_api_protocols import RuntimeApiLocalMutation
from app.services.runtime_api_validation import validate_runtime_api_idempotency_replay


class RuntimeApiIdempotencyPersistenceError(RuntimeError):
    """A bounded persistence failure without SQL detail."""


class RuntimeApiIdempotencyTransactionRequiredError(RuntimeApiIdempotencyPersistenceError):
    """The caller did not provide an active transaction."""


def _lock_material(identity: RuntimeApiCommandIdentity) -> bytes:
    values = (
        str(identity.tenant_id),
        str(identity.organization_id),
        str(identity.principal_id),
        identity.operation.value,
        identity.command_version,
        identity.idempotency_key,
    )
    return b"".join(
        len(value.encode("ascii")).to_bytes(2, "big") + value.encode("ascii") for value in values
    )


def _advisory_lock_key(identity: RuntimeApiCommandIdentity) -> int:
    return int.from_bytes(hashlib.sha256(_lock_material(identity)).digest()[:8], "big", signed=True)


def _receipt(record: RuntimeApiIdempotencyReceiptRecord) -> RuntimeApiIdempotencyReceipt:
    identity = RuntimeApiCommandIdentity(
        command_id=record.command_id,
        operation=RuntimeApiOperation(record.operation),
        tenant_id=record.tenant_id,
        organization_id=record.organization_id,
        principal_id=record.principal_id,
        command_version=record.command_version,
        idempotency_key=record.idempotency_key,
        command_digest=record.command_digest,
        correlation_reference=record.command_correlation_reference,
    )
    projection = RuntimeApiStatusProjection(
        invocation_reference=record.invocation_reference,
        status=RuntimeApiPublicStatus(record.public_status),
        status_reference=record.status_reference,
        correlation_reference=record.result_correlation_reference,
        observed_at=record.observed_at,
    )
    return RuntimeApiIdempotencyReceipt(
        receipt_id=record.receipt_id,
        identity=identity,
        safe_result=RuntimeApiSafeResult(
            result_reference=record.result_reference, projection=projection
        ),
        committed_at=record.committed_at,
    )


class SQLAlchemyRuntimeApiIdempotencyTransaction:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(
        self,
        identity: RuntimeApiCommandIdentity,
        facts: RuntimeApiIdempotencyCommitFacts,
        mutation: RuntimeApiLocalMutation,
    ) -> RuntimeApiIdempotencyCommitResult:
        if not self._session.in_transaction():
            raise RuntimeApiIdempotencyTransactionRequiredError(
                "active caller transaction required"
            )
        if identity.operation not in {
            RuntimeApiOperation.SUBMIT_INVOCATION,
            RuntimeApiOperation.REQUEST_RECONCILIATION,
        }:
            raise RuntimeApiIdempotencyPersistenceError("unsupported mutation operation")
        try:
            await self._session.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": _advisory_lock_key(identity)},
            )
            record = await self._session.scalar(
                select(RuntimeApiIdempotencyReceiptRecord).where(
                    RuntimeApiIdempotencyReceiptRecord.tenant_id == identity.tenant_id,
                    RuntimeApiIdempotencyReceiptRecord.organization_id == identity.organization_id,
                    RuntimeApiIdempotencyReceiptRecord.principal_id == identity.principal_id,
                    RuntimeApiIdempotencyReceiptRecord.operation == identity.operation.value,
                    RuntimeApiIdempotencyReceiptRecord.command_version == identity.command_version,
                    RuntimeApiIdempotencyReceiptRecord.idempotency_key == identity.idempotency_key,
                )
            )
            if record is not None:
                stored = validate_runtime_api_idempotency_replay(identity, _receipt(record))
                return RuntimeApiIdempotencyCommitResult(
                    disposition=RuntimeApiIdempotencyDisposition.EXACT_REPLAY,
                    receipt=stored,
                    safe_result=stored.safe_result,
                )
            safe_result = await mutation()
            if not isinstance(safe_result, RuntimeApiSafeResult):
                raise RuntimeApiIdempotencyPersistenceError(
                    "mutation returned an invalid safe result"
                )
            receipt = RuntimeApiIdempotencyReceipt(
                receipt_id=facts.receipt_id,
                identity=identity,
                safe_result=safe_result,
                committed_at=facts.committed_at,
            )
            projection = safe_result.projection
            self._session.add(
                RuntimeApiIdempotencyReceiptRecord(
                    receipt_id=facts.receipt_id,
                    tenant_id=identity.tenant_id,
                    organization_id=identity.organization_id,
                    principal_id=identity.principal_id,
                    operation=identity.operation.value,
                    command_version=identity.command_version,
                    idempotency_key=identity.idempotency_key,
                    command_digest=identity.command_digest,
                    command_id=identity.command_id,
                    command_correlation_reference=identity.correlation_reference,
                    result_reference=safe_result.result_reference,
                    invocation_reference=projection.invocation_reference,
                    public_status=projection.status.value,
                    status_reference=projection.status_reference,
                    result_correlation_reference=projection.correlation_reference,
                    observed_at=projection.observed_at,
                    committed_at=facts.committed_at,
                )
            )
            await self._session.flush()
            return RuntimeApiIdempotencyCommitResult(
                disposition=RuntimeApiIdempotencyDisposition.COMMITTED,
                receipt=receipt,
                safe_result=safe_result,
            )
        except SQLAlchemyError as exc:
            raise RuntimeApiIdempotencyPersistenceError(
                "transport idempotency persistence failed"
            ) from exc


__all__ = (
    "RuntimeApiIdempotencyPersistenceError",
    "RuntimeApiIdempotencyTransactionRequiredError",
    "SQLAlchemyRuntimeApiIdempotencyTransaction",
)
