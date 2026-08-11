"""Exact append-only repositories for CP9 Registry persistence."""

from typing import cast

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.runtime_registry import (
    RuntimeReconciliationRequestRecord,
    RuntimeRegistryAdmissionBindingRecord,
    RuntimeRegistryPermitBindingRecord,
    RuntimeRegistryResolutionDecisionRecord,
    RuntimeRegistryResolutionRequestRecord,
    RuntimeRegistrySnapshotEntryRecord,
    RuntimeRegistrySnapshotRecord,
)
from app.runtime.persistence.errors import (
    RuntimePersistenceConflictError,
    RuntimePersistenceError,
    RuntimeRegistryPersistenceBindingError,
    RuntimeRegistryPersistenceNotFoundError,
)
from app.runtime.persistence.registry_serialization import (
    RuntimeRegistryPayloadType,
    deserialize_registry_payload,
    serialize_registry_payload,
    validate_registry_graph,
)
from app.runtime.ports import RuntimeApiLocalWriteSetStage, RuntimeApiPersistenceBindingRead
from app.runtime.registry import (
    RuntimeActionRegistrySnapshot,
    RuntimeActionResolutionDecision,
    RuntimeActionResolutionRequest,
)


class SQLAlchemyRuntimeRegistryRepository:
    """Persist and load one exact Registry/resolution/admission graph."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append_binding(self, binding: RuntimeApiPersistenceBindingRead) -> None:
        facts = binding.registry_resolution_admission
        snapshot = facts.snapshot
        request = facts.resolution_request
        decision = facts.resolution_decision
        validate_registry_graph(snapshot, request, decision)
        try:
            self._session.add(
                RuntimeRegistrySnapshotRecord(
                    runtime_registry_snapshot_id=snapshot.runtime_registry_snapshot_id,
                    registry_revision=snapshot.registry_revision,
                    tenant_id=snapshot.tenant_id,
                    organization_id=snapshot.organization_id,
                    classification=snapshot.classification.value,
                    root_lineage_id=snapshot.root_lineage_id,
                    root_lineage_digest_reference=snapshot.root_lineage_digest_reference,
                    snapshot_digest_reference=snapshot.snapshot_digest_reference,
                    runtime_registry_version=(snapshot.contract_version.runtime_registry_version),
                    runtime_registry_contract_version=(
                        snapshot.contract_version.runtime_registry_contract_version
                    ),
                    runtime_registry_schema_version=(
                        snapshot.contract_version.runtime_registry_schema_version
                    ),
                    definition_count=snapshot.audit_metadata.definition_count,
                    active_count=snapshot.audit_metadata.active_count,
                    disabled_count=snapshot.audit_metadata.disabled_count,
                    retired_count=snapshot.audit_metadata.retired_count,
                    invalidated_count=snapshot.audit_metadata.invalidated_count,
                    audit_digest_reference=snapshot.audit_metadata.audit_digest_reference,
                    snapshot_payload=serialize_registry_payload(snapshot),
                    created_at=snapshot.created_at,
                )
            )
            await self._session.flush()
            for position, entry in enumerate(snapshot.entries):
                action = entry.action_definition.identity
                self._session.add(
                    RuntimeRegistrySnapshotEntryRecord(
                        runtime_registry_snapshot_entry_id=entry.runtime_registry_snapshot_entry_id,
                        runtime_registry_snapshot_id=snapshot.runtime_registry_snapshot_id,
                        registry_revision=snapshot.registry_revision,
                        canonical_position=position,
                        action_definition_id=action.action_definition_id,
                        action=action.action,
                        action_version=action.action_version,
                        status=entry.status.value,
                        entry_payload=serialize_registry_payload(entry),
                        recorded_at=entry.recorded_at,
                    )
                )
            await self._session.flush()
            self._session.add(
                RuntimeRegistryResolutionRequestRecord(
                    runtime_action_resolution_request_id=request.runtime_action_resolution_request_id,
                    runtime_registry_snapshot_id=snapshot.runtime_registry_snapshot_id,
                    registry_revision=snapshot.registry_revision,
                    tenant_id=request.tenant_id,
                    organization_id=request.organization_id,
                    classification=request.classification.value,
                    root_lineage_id=request.root_lineage_id,
                    root_lineage_digest_reference=request.root_lineage_digest_reference,
                    request_payload=serialize_registry_payload(request),
                    requested_at=request.requested_at,
                )
            )
            await self._session.flush()
            self._session.add(
                RuntimeRegistryResolutionDecisionRecord(
                    runtime_action_resolution_decision_id=decision.runtime_action_resolution_decision_id,
                    runtime_action_resolution_request_id=request.runtime_action_resolution_request_id,
                    runtime_registry_snapshot_id=snapshot.runtime_registry_snapshot_id,
                    registry_revision=snapshot.registry_revision,
                    tenant_id=decision.tenant_id,
                    organization_id=decision.organization_id,
                    classification=decision.classification.value,
                    decision_status=decision.decision_status.value,
                    resolved_snapshot_entry_id=decision.resolved_snapshot_entry_id,
                    decision_payload=serialize_registry_payload(decision),
                    decided_at=decision.decided_at,
                )
            )
            await self._session.flush()
            self._session.add(
                RuntimeRegistryAdmissionBindingRecord(
                    runtime_admission_decision_id=binding.admission.record_id,
                    admission_expected_revision=binding.admission.expected_revision,
                    runtime_execution_request_id=binding.execution_request.record_id,
                    execution_request_expected_revision=binding.execution_request.expected_revision,
                    runtime_action_resolution_request_id=request.runtime_action_resolution_request_id,
                    runtime_action_resolution_decision_id=decision.runtime_action_resolution_decision_id,
                    runtime_registry_snapshot_id=snapshot.runtime_registry_snapshot_id,
                    registry_revision=snapshot.registry_revision,
                    snapshot_digest_reference=snapshot.snapshot_digest_reference,
                    tenant_id=binding.scope.tenant_id,
                    organization_id=binding.scope.organization_id,
                    classification=binding.scope.classification.value,
                    root_lineage_id=binding.scope.root_lineage_id,
                    root_lineage_digest_reference=binding.scope.root_lineage_digest_reference,
                    bound_at=binding.requested_at,
                )
            )
            await self._session.flush()
            for position, permit in enumerate(binding.permits):
                self._session.add(
                    RuntimeRegistryPermitBindingRecord(
                        runtime_admission_decision_id=binding.admission.record_id,
                        permit_id=permit.permit_id,
                        expected_revision=permit.expected_revision,
                        canonical_position=position,
                    )
                )
            await self._session.flush()
        except IntegrityError as exc:
            raise RuntimePersistenceConflictError(
                "Registry persistence identity conflicted"
            ) from exc
        except SQLAlchemyError as exc:
            raise RuntimePersistenceError("Registry persistence append failed") from exc

    async def read_exact(
        self, expected: RuntimeApiPersistenceBindingRead
    ) -> RuntimeApiPersistenceBindingRead:
        registry = expected.registry
        scope = expected.scope
        snapshot_row = await self._session.scalar(
            select(RuntimeRegistrySnapshotRecord)
            .where(
                RuntimeRegistrySnapshotRecord.runtime_registry_snapshot_id
                == registry.runtime_registry_snapshot_id,
                RuntimeRegistrySnapshotRecord.registry_revision == registry.registry_revision,
                RuntimeRegistrySnapshotRecord.snapshot_digest_reference
                == registry.snapshot_digest_reference,
                RuntimeRegistrySnapshotRecord.tenant_id == scope.tenant_id,
                RuntimeRegistrySnapshotRecord.organization_id == scope.organization_id,
                RuntimeRegistrySnapshotRecord.classification == scope.classification.value,
                RuntimeRegistrySnapshotRecord.root_lineage_id == scope.root_lineage_id,
                RuntimeRegistrySnapshotRecord.root_lineage_digest_reference
                == scope.root_lineage_digest_reference,
            )
            .with_for_update()
        )
        request_row = await self._session.get(
            RuntimeRegistryResolutionRequestRecord,
            registry.runtime_action_resolution_request_id,
            with_for_update=True,
        )
        decision_row = await self._session.get(
            RuntimeRegistryResolutionDecisionRecord,
            registry.runtime_action_resolution_decision_id,
            with_for_update=True,
        )
        admission_row = await self._session.get(
            RuntimeRegistryAdmissionBindingRecord,
            expected.admission.record_id,
            with_for_update=True,
        )
        if any(item is None for item in (snapshot_row, request_row, decision_row, admission_row)):
            raise RuntimeRegistryPersistenceNotFoundError(
                "exact Registry persistence binding is unavailable"
            )
        assert snapshot_row is not None
        assert request_row is not None
        assert decision_row is not None
        assert admission_row is not None
        entry_rows = (
            await self._session.scalars(
                select(RuntimeRegistrySnapshotEntryRecord)
                .where(
                    RuntimeRegistrySnapshotEntryRecord.runtime_registry_snapshot_id
                    == registry.runtime_registry_snapshot_id,
                    RuntimeRegistrySnapshotEntryRecord.registry_revision
                    == registry.registry_revision,
                )
                .order_by(RuntimeRegistrySnapshotEntryRecord.canonical_position)
                .with_for_update()
            )
        ).all()
        permit_rows = (
            await self._session.scalars(
                select(RuntimeRegistryPermitBindingRecord)
                .where(
                    RuntimeRegistryPermitBindingRecord.runtime_admission_decision_id
                    == expected.admission.record_id
                )
                .order_by(RuntimeRegistryPermitBindingRecord.canonical_position)
                .with_for_update()
            )
        ).all()
        snapshot = cast(
            RuntimeActionRegistrySnapshot,
            deserialize_registry_payload(
                RuntimeRegistryPayloadType.SNAPSHOT, snapshot_row.snapshot_payload
            ),
        )
        request = cast(
            RuntimeActionResolutionRequest,
            deserialize_registry_payload(
                RuntimeRegistryPayloadType.RESOLUTION_REQUEST, request_row.request_payload
            ),
        )
        decision = cast(
            RuntimeActionResolutionDecision,
            deserialize_registry_payload(
                RuntimeRegistryPayloadType.RESOLUTION_DECISION, decision_row.decision_payload
            ),
        )
        validate_registry_graph(snapshot, request, decision)
        relational_entries = tuple(
            deserialize_registry_payload(RuntimeRegistryPayloadType.ENTRY, row.entry_payload)
            for row in entry_rows
        )
        actual_permits = tuple((row.permit_id, row.expected_revision) for row in permit_rows)
        expected_permits = tuple(
            (item.permit_id, item.expected_revision) for item in expected.permits
        )
        actual_binding = (
            admission_row.runtime_execution_request_id,
            admission_row.execution_request_expected_revision,
            admission_row.runtime_admission_decision_id,
            admission_row.admission_expected_revision,
            admission_row.runtime_action_resolution_request_id,
            admission_row.runtime_action_resolution_decision_id,
            admission_row.runtime_registry_snapshot_id,
            admission_row.registry_revision,
            admission_row.snapshot_digest_reference,
            admission_row.tenant_id,
            admission_row.organization_id,
            admission_row.classification,
            admission_row.root_lineage_id,
            admission_row.root_lineage_digest_reference,
        )
        expected_binding = (
            expected.execution_request.record_id,
            expected.execution_request.expected_revision,
            expected.admission.record_id,
            expected.admission.expected_revision,
            registry.runtime_action_resolution_request_id,
            registry.runtime_action_resolution_decision_id,
            registry.runtime_registry_snapshot_id,
            registry.registry_revision,
            registry.snapshot_digest_reference,
            scope.tenant_id,
            scope.organization_id,
            scope.classification.value,
            scope.root_lineage_id,
            scope.root_lineage_digest_reference,
        )
        expected_facts = expected.registry_resolution_admission
        if (
            snapshot != expected_facts.snapshot
            or relational_entries != snapshot.entries
            or request != expected_facts.resolution_request
            or decision != expected_facts.resolution_decision
            or actual_binding != expected_binding
            or actual_permits != expected_permits
        ):
            raise RuntimeRegistryPersistenceBindingError(
                "stored Registry persistence binding differs"
            )
        return expected

    async def append_reconciliation_request(self, stage: RuntimeApiLocalWriteSetStage) -> None:
        request = stage.reconciliation_request
        if request is None:
            raise RuntimeRegistryPersistenceBindingError(
                "reconciliation stage requires one request"
            )
        matches = (
            await self._session.scalars(
                select(RuntimeReconciliationRequestRecord)
                .where(
                    or_(
                        RuntimeReconciliationRequestRecord.runtime_effect_reconciliation_request_id
                        == request.runtime_effect_reconciliation_request_id,
                        RuntimeReconciliationRequestRecord.local_write_set_id
                        == stage.local_write_set_id,
                        RuntimeReconciliationRequestRecord.transport_receipt_id
                        == stage.transport_receipt_id,
                    )
                )
                .with_for_update()
            )
        ).all()
        expected = (
            request.runtime_effect_reconciliation_request_id,
            request.runtime_effect_id,
            request.tenant_id,
            request.organization_id,
            request.classification.value,
            stage.binding.admission.record_id,
            stage.binding.admission.expected_revision,
            stage.binding.execution_request.record_id,
            stage.binding.execution_request.expected_revision,
            stage.binding.registry.runtime_action_resolution_request_id,
            stage.binding.registry.runtime_action_resolution_decision_id,
            stage.binding.registry.runtime_registry_snapshot_id,
            stage.binding.registry.registry_revision,
            stage.binding.registry.snapshot_digest_reference,
            stage.binding.scope.root_lineage_id,
            stage.binding.scope.root_lineage_digest_reference,
            stage.local_write_set_id,
            stage.transport_receipt_id,
            stage.write_set_digest_reference,
            serialize_registry_payload(request),
            request.requested_at,
            stage.staged_at,
        )
        if matches:
            if len(matches) != 1:
                raise RuntimeRegistryPersistenceBindingError(
                    "reconciliation request identity is ambiguous"
                )
            row = matches[0]
            actual = (
                row.runtime_effect_reconciliation_request_id,
                row.runtime_effect_id,
                row.tenant_id,
                row.organization_id,
                row.classification,
                row.runtime_admission_decision_id,
                row.admission_expected_revision,
                row.runtime_execution_request_id,
                row.execution_request_expected_revision,
                row.runtime_action_resolution_request_id,
                row.runtime_action_resolution_decision_id,
                row.runtime_registry_snapshot_id,
                row.registry_revision,
                row.snapshot_digest_reference,
                row.root_lineage_id,
                row.root_lineage_digest_reference,
                row.local_write_set_id,
                row.transport_receipt_id,
                row.write_set_digest_reference,
                row.request_payload,
                row.requested_at,
                row.staged_at,
            )
            if actual == expected:
                return
            raise RuntimePersistenceConflictError("reconciliation request identity conflicted")
        try:
            self._session.add(
                RuntimeReconciliationRequestRecord(
                    runtime_effect_reconciliation_request_id=(
                        request.runtime_effect_reconciliation_request_id
                    ),
                    runtime_effect_id=request.runtime_effect_id,
                    tenant_id=request.tenant_id,
                    organization_id=request.organization_id,
                    classification=request.classification.value,
                    runtime_admission_decision_id=stage.binding.admission.record_id,
                    admission_expected_revision=stage.binding.admission.expected_revision,
                    runtime_execution_request_id=stage.binding.execution_request.record_id,
                    execution_request_expected_revision=(
                        stage.binding.execution_request.expected_revision
                    ),
                    runtime_action_resolution_request_id=(
                        stage.binding.registry.runtime_action_resolution_request_id
                    ),
                    runtime_action_resolution_decision_id=(
                        stage.binding.registry.runtime_action_resolution_decision_id
                    ),
                    runtime_registry_snapshot_id=(
                        stage.binding.registry.runtime_registry_snapshot_id
                    ),
                    registry_revision=stage.binding.registry.registry_revision,
                    snapshot_digest_reference=stage.binding.registry.snapshot_digest_reference,
                    root_lineage_id=stage.binding.scope.root_lineage_id,
                    root_lineage_digest_reference=(
                        stage.binding.scope.root_lineage_digest_reference
                    ),
                    local_write_set_id=stage.local_write_set_id,
                    transport_receipt_id=stage.transport_receipt_id,
                    write_set_digest_reference=stage.write_set_digest_reference,
                    request_payload=serialize_registry_payload(request),
                    requested_at=request.requested_at,
                    staged_at=stage.staged_at,
                )
            )
            await self._session.flush()
        except IntegrityError as exc:
            raise RuntimePersistenceConflictError(
                "reconciliation request identity conflicted"
            ) from exc
        except SQLAlchemyError as exc:
            raise RuntimePersistenceError("reconciliation request persistence failed") from exc


__all__ = ("SQLAlchemyRuntimeRegistryRepository",)
