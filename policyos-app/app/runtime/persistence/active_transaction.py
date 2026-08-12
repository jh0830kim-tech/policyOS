"""One-shot CP9 persistence capability bound to a caller-owned transaction."""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction

from app.runtime.persistence.errors import (
    RuntimePersistenceError,
    RuntimePersistenceTransactionError,
)
from app.runtime.persistence.logical_result_repositories import (
    SQLAlchemyRuntimeLogicalExecutionResultRepository,
)
from app.runtime.persistence.registry_repositories import SQLAlchemyRuntimeRegistryRepository
from app.runtime.persistence.transaction import _persist_runtime_atomic_write_set
from app.runtime.ports import (
    RuntimeApiActiveTransactionContext,
    RuntimeApiExecutionStateRevisionReadResult,
    RuntimeApiLocalWriteSetOperation,
    RuntimeApiLocalWriteSetStage,
    RuntimeApiLocalWriteSetStageResult,
    RuntimeApiLogicalExecutionResultMutationPresent,
    RuntimeApiLogicalExecutionResultRevisionReadResult,
    RuntimeApiPersistenceBindingRead,
    RuntimeApiQueryProjectionLocator,
    validate_runtime_atomic_write_set,
)


class SQLAlchemyRuntimeApiActiveTransactionPersistence:
    """Execute one read or stage against the exact captured root transaction."""

    def __init__(
        self,
        session: AsyncSession,
        context: RuntimeApiActiveTransactionContext,
        root_transaction: AsyncSessionTransaction,
    ) -> None:
        self._session = session
        self._context = context
        self._root_transaction = root_transaction
        self._used = False

    def _enter(self, context: RuntimeApiActiveTransactionContext) -> None:
        if self._used:
            raise RuntimePersistenceTransactionError(
                "active-transaction persistence capability is one-shot"
            )
        self._used = True
        if context != self._context:
            raise RuntimePersistenceTransactionError("transaction context differs")
        if not self._session.in_transaction():
            raise RuntimePersistenceTransactionError("active caller transaction required")
        if self._session.in_nested_transaction():
            raise RuntimePersistenceTransactionError("nested transaction is prohibited")
        if self._session.get_transaction() is not self._root_transaction:
            raise RuntimePersistenceTransactionError("caller root transaction was replaced")

    async def read_exact(
        self,
        context: RuntimeApiActiveTransactionContext,
        request: RuntimeApiPersistenceBindingRead,
    ) -> RuntimeApiPersistenceBindingRead:
        self._enter(context)
        try:
            return await SQLAlchemyRuntimeRegistryRepository(self._session).read_exact(request)
        except RuntimePersistenceError:
            raise
        except SQLAlchemyError as exc:
            raise RuntimePersistenceError("active Registry read failed") from exc

    async def read_exact_state_revision(
        self,
        context: RuntimeApiActiveTransactionContext,
        locator: RuntimeApiQueryProjectionLocator,
    ) -> RuntimeApiExecutionStateRevisionReadResult:
        self._enter(context)
        try:
            return await SQLAlchemyRuntimeLogicalExecutionResultRepository(
                self._session
            ).read_exact_state_revision(locator)
        except RuntimePersistenceError:
            raise
        except SQLAlchemyError as exc:
            raise RuntimePersistenceError("active exact state read failed") from exc

    async def read_exact_logical_execution_result_revision(
        self,
        context: RuntimeApiActiveTransactionContext,
        locator: RuntimeApiQueryProjectionLocator,
    ) -> RuntimeApiLogicalExecutionResultRevisionReadResult:
        self._enter(context)
        try:
            return await SQLAlchemyRuntimeLogicalExecutionResultRepository(
                self._session
            ).read_exact_logical_execution_result_revision(locator)
        except RuntimePersistenceError:
            raise
        except SQLAlchemyError as exc:
            raise RuntimePersistenceError("active exact logical-result read failed") from exc

    async def stage_local_write_set(
        self,
        context: RuntimeApiActiveTransactionContext,
        stage: RuntimeApiLocalWriteSetStage,
    ) -> RuntimeApiLocalWriteSetStageResult:
        self._enter(context)
        try:
            if stage.operation is RuntimeApiLocalWriteSetOperation.SUBMIT_INVOCATION:
                if stage.write_set is None:
                    raise RuntimePersistenceTransactionError(
                        "submission stage requires one atomic write set"
                    )
                validate_runtime_atomic_write_set(stage.write_set)
                await _persist_runtime_atomic_write_set(
                    self._session,
                    stage.write_set,
                    stored_at=stage.staged_at,
                )
                if isinstance(
                    stage.logical_execution_result,
                    RuntimeApiLogicalExecutionResultMutationPresent,
                ):
                    await SQLAlchemyRuntimeLogicalExecutionResultRepository(
                        self._session
                    ).append_from_stage(stage)
            elif stage.operation is RuntimeApiLocalWriteSetOperation.REQUEST_RECONCILIATION:
                await SQLAlchemyRuntimeRegistryRepository(
                    self._session
                ).append_reconciliation_request(stage)
            else:
                raise RuntimePersistenceTransactionError(
                    "read-only operation cannot stage a write set"
                )
        except RuntimePersistenceError:
            raise
        except SQLAlchemyError as exc:
            raise RuntimePersistenceError("active local write-set stage failed") from exc
        return RuntimeApiLocalWriteSetStageResult(
            local_write_set_id=stage.local_write_set_id,
            transport_receipt_id=stage.transport_receipt_id,
            operation=stage.operation,
            write_set_digest_reference=stage.write_set_digest_reference,
            staged_mutation_count=1,
        )


class SQLAlchemyRuntimeApiActiveTransactionPersistenceFactory:
    """Capture the exact caller session and current root transaction object."""

    def __call__(
        self,
        session: AsyncSession,
        context: RuntimeApiActiveTransactionContext,
    ) -> SQLAlchemyRuntimeApiActiveTransactionPersistence:
        if not session.in_transaction():
            raise RuntimePersistenceTransactionError("active caller transaction required")
        if session.in_nested_transaction():
            raise RuntimePersistenceTransactionError("nested transaction is prohibited")
        root = session.get_transaction()
        if root is None:
            raise RuntimePersistenceTransactionError("caller root transaction is unavailable")
        return SQLAlchemyRuntimeApiActiveTransactionPersistence(session, context, root)


__all__ = (
    "SQLAlchemyRuntimeApiActiveTransactionPersistence",
    "SQLAlchemyRuntimeApiActiveTransactionPersistenceFactory",
)
