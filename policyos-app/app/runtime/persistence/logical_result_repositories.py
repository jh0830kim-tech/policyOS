"""Exact append-only persistence for CP9 logical execution results."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.runtime_logical_result import (
    RuntimeLogicalExecutionResultRecord,
    RuntimeLogicalExecutionResultRevisionRecord,
)
from app.runtime.persistence.errors import (
    RuntimePersistenceConflictError,
    RuntimePersistenceError,
)
from app.runtime.persistence.logical_result_serialization import (
    deserialize_logical_execution_result,
    serialize_logical_execution_result,
)
from app.runtime.persistence.models import RuntimeRecordRevision
from app.runtime.persistence.serialization import (
    RuntimePersistenceRecordType,
    deserialize_runtime_record,
)
from app.runtime.ports import (
    RuntimeApiExecutionStateRevisionReadResult,
    RuntimeApiLocalWriteSetStage,
    RuntimeApiLogicalExecutionResult,
    RuntimeApiLogicalExecutionResultMutationPresent,
    RuntimeApiLogicalExecutionResultRevisionReadResult,
    RuntimeApiQueryProjectionLocator,
    RuntimeApiQueryResultPresentLocator,
)
from app.runtime.state import RuntimeExecutionStateRecord


def _identity_values(result: RuntimeApiLogicalExecutionResult) -> tuple[object, ...]:
    return (
        result.runtime_logical_execution_result_id,
        result.scope.tenant_id,
        result.scope.organization_id,
        result.scope.classification.value,
        result.execution_request.record_id,
        result.attempt_id,
        result.scope.root_lineage_id,
        result.scope.root_lineage_digest_reference,
    )


def _stored_identity_values(
    stored: RuntimeLogicalExecutionResultRecord,
) -> tuple[object, ...]:
    return (
        stored.runtime_logical_execution_result_id,
        stored.tenant_id,
        stored.organization_id,
        stored.classification,
        stored.runtime_execution_request_id,
        stored.attempt_id,
        stored.root_lineage_id,
        stored.root_lineage_digest_reference,
    )


def _revision_values(result: RuntimeApiLogicalExecutionResult) -> tuple[object, ...]:
    return (
        result.runtime_logical_execution_result_id,
        result.result_revision,
        result.scope.tenant_id,
        result.scope.organization_id,
        result.scope.classification.value,
        result.execution_request.record_id,
        result.execution_request.expected_revision,
        result.attempt_id,
        result.scope.root_lineage_id,
        result.scope.root_lineage_digest_reference,
        result.execution_state.record_id,
        result.execution_state.expected_revision,
        result.audit_trail.record_id,
        result.audit_trail.expected_revision,
        result.result_reference,
        result.result_digest_reference,
        result.result_payload_provenance_reference,
        result.produced_at,
    )


def _stored_revision_values(
    stored: RuntimeLogicalExecutionResultRevisionRecord,
) -> tuple[object, ...]:
    return (
        stored.runtime_logical_execution_result_id,
        stored.result_revision,
        stored.tenant_id,
        stored.organization_id,
        stored.classification,
        stored.runtime_execution_request_id,
        stored.execution_request_expected_revision,
        stored.attempt_id,
        stored.root_lineage_id,
        stored.root_lineage_digest_reference,
        stored.runtime_execution_state_record_id,
        stored.execution_state_expected_revision,
        stored.runtime_audit_trail_id,
        stored.audit_trail_expected_revision,
        stored.result_reference,
        stored.result_digest_reference,
        stored.result_payload_provenance_reference,
        stored.produced_at,
    )


class SQLAlchemyRuntimeLogicalExecutionResultRepository:
    """Append and read explicitly named logical-result revisions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append_from_stage(self, stage: RuntimeApiLocalWriteSetStage) -> None:
        mutation = stage.logical_execution_result
        if not isinstance(mutation, RuntimeApiLogicalExecutionResultMutationPresent):
            return
        result = mutation.logical_execution_result
        try:
            identity = (
                await self._session.execute(
                    select(RuntimeLogicalExecutionResultRecord)
                    .where(
                        RuntimeLogicalExecutionResultRecord.runtime_logical_execution_result_id
                        == result.runtime_logical_execution_result_id
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if identity is None:
                if result.result_revision != 1:
                    raise RuntimePersistenceConflictError(
                        "first logical execution-result revision must be one"
                    )
                identity = RuntimeLogicalExecutionResultRecord(
                    runtime_logical_execution_result_id=(
                        result.runtime_logical_execution_result_id
                    ),
                    tenant_id=result.scope.tenant_id,
                    organization_id=result.scope.organization_id,
                    classification=result.scope.classification.value,
                    runtime_execution_request_id=result.execution_request.record_id,
                    attempt_id=result.attempt_id,
                    root_lineage_id=result.scope.root_lineage_id,
                    root_lineage_digest_reference=(result.scope.root_lineage_digest_reference),
                )
                self._session.add(identity)
            elif _stored_identity_values(identity) != _identity_values(result):
                raise RuntimePersistenceConflictError("logical execution-result identity differs")
            self._session.add(
                RuntimeLogicalExecutionResultRevisionRecord(
                    runtime_logical_execution_result_id=(
                        result.runtime_logical_execution_result_id
                    ),
                    result_revision=result.result_revision,
                    tenant_id=result.scope.tenant_id,
                    organization_id=result.scope.organization_id,
                    classification=result.scope.classification.value,
                    runtime_execution_request_id=result.execution_request.record_id,
                    execution_request_expected_revision=(
                        result.execution_request.expected_revision
                    ),
                    attempt_id=result.attempt_id,
                    root_lineage_id=result.scope.root_lineage_id,
                    root_lineage_digest_reference=(result.scope.root_lineage_digest_reference),
                    runtime_execution_state_record_id=result.execution_state.record_id,
                    execution_state_expected_revision=(result.execution_state.expected_revision),
                    runtime_audit_trail_id=result.audit_trail.record_id,
                    audit_trail_expected_revision=result.audit_trail.expected_revision,
                    execution_request_record_type=(
                        RuntimePersistenceRecordType.EXECUTION_REQUEST.value
                    ),
                    execution_state_record_type=(
                        RuntimePersistenceRecordType.EXECUTION_STATE.value
                    ),
                    audit_trail_record_type=RuntimePersistenceRecordType.AUDIT_TRAIL.value,
                    result_reference=result.result_reference,
                    result_digest_reference=result.result_digest_reference,
                    result_payload_provenance_reference=(
                        result.result_payload_provenance_reference
                    ),
                    result_payload=serialize_logical_execution_result(result),
                    produced_at=result.produced_at,
                    stored_at=stage.staged_at,
                )
            )
            await self._session.flush()
        except RuntimePersistenceError:
            raise
        except IntegrityError as exc:
            raise RuntimePersistenceConflictError(
                "logical execution-result relational constraint conflicted"
            ) from exc
        except SQLAlchemyError as exc:
            raise RuntimePersistenceError("logical execution-result append failed") from exc

    async def read_exact_state_revision(
        self,
        locator: RuntimeApiQueryProjectionLocator,
    ) -> RuntimeApiExecutionStateRevisionReadResult:
        stored = (
            await self._session.execute(
                select(RuntimeRecordRevision).where(
                    RuntimeRecordRevision.record_type
                    == RuntimePersistenceRecordType.EXECUTION_STATE.value,
                    RuntimeRecordRevision.tenant_id == locator.scope.tenant_id,
                    RuntimeRecordRevision.organization_id == locator.scope.organization_id,
                    RuntimeRecordRevision.classification == locator.scope.classification.value,
                    RuntimeRecordRevision.record_id == locator.execution_state.record_id,
                    RuntimeRecordRevision.record_revision
                    == locator.execution_state.expected_revision,
                )
            )
        ).scalar_one_or_none()
        if stored is None:
            raise RuntimePersistenceError("exact execution-state revision is unavailable")
        state = deserialize_runtime_record(
            RuntimePersistenceRecordType.EXECUTION_STATE,
            stored.payload,
        )
        if not isinstance(state, RuntimeExecutionStateRecord):
            raise RuntimePersistenceError("stored state payload type differs")
        if (
            state.runtime_execution_state_record_id,
            state.current_revision,
            state.scope.runtime_execution_request_id,
            state.scope.attempt_id,
            state.scope.tenant_id,
            state.scope.organization_id,
            state.scope.classification,
            state.scope.root_lineage_id,
            state.scope.root_lineage_digest_reference,
        ) != (
            locator.execution_state.record_id,
            locator.execution_state.expected_revision,
            locator.execution_request.record_id,
            locator.attempt_id,
            locator.scope.tenant_id,
            locator.scope.organization_id,
            locator.scope.classification,
            locator.scope.root_lineage_id,
            locator.scope.root_lineage_digest_reference,
        ):
            raise RuntimePersistenceError("stored state differs from exact locator")
        return RuntimeApiExecutionStateRevisionReadResult(
            locator=locator,
            state=state.current_state,
            record_digest_reference=stored.record_digest_reference,
            observed_at=locator.located_at,
        )

    async def read_exact_logical_execution_result_revision(
        self,
        locator: RuntimeApiQueryProjectionLocator,
    ) -> RuntimeApiLogicalExecutionResultRevisionReadResult:
        if not isinstance(locator.result, RuntimeApiQueryResultPresentLocator):
            raise RuntimePersistenceError("logical-result read requires a present locator")
        stored = (
            await self._session.execute(
                select(RuntimeLogicalExecutionResultRevisionRecord).where(
                    RuntimeLogicalExecutionResultRevisionRecord.runtime_logical_execution_result_id
                    == locator.result.logical_execution_result.record_id,
                    RuntimeLogicalExecutionResultRevisionRecord.result_revision
                    == locator.result.logical_execution_result.expected_revision,
                    RuntimeLogicalExecutionResultRevisionRecord.tenant_id
                    == locator.scope.tenant_id,
                    RuntimeLogicalExecutionResultRevisionRecord.organization_id
                    == locator.scope.organization_id,
                    RuntimeLogicalExecutionResultRevisionRecord.classification
                    == locator.scope.classification.value,
                )
            )
        ).scalar_one_or_none()
        if stored is None:
            raise RuntimePersistenceError("exact logical execution-result revision is unavailable")
        result = deserialize_logical_execution_result(stored.result_payload)
        if _stored_revision_values(stored) != _revision_values(result):
            raise RuntimePersistenceError(
                "stored logical execution-result columns differ from payload"
            )
        return RuntimeApiLogicalExecutionResultRevisionReadResult(
            locator=locator,
            logical_execution_result=result,
            observed_at=locator.located_at,
        )


__all__ = ("SQLAlchemyRuntimeLogicalExecutionResultRepository",)
