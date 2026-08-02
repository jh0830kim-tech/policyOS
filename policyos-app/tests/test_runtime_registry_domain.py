"""Focused network-free tests for the immutable Runtime Registry domain."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.runtime.authority import (
    RuntimeExecutionEnvironment,
    RuntimePermitSourceType,
    RuntimeRiskLevel,
)
from app.runtime.planning import ExecutionActionReference
from app.runtime.registry import (
    RuntimeActionAdapterReference,
    RuntimeActionCapability,
    RuntimeActionCompensationEligibility,
    RuntimeActionDefinition,
    RuntimeActionDestinationRequirement,
    RuntimeActionIdempotencyRequirement,
    RuntimeActionIdentity,
    RuntimeActionPermitRequirement,
    RuntimeActionRegistrySnapshot,
    RuntimeActionResolutionDecision,
    RuntimeActionResolutionReasonCode,
    RuntimeActionResolutionRequest,
    RuntimeActionResolutionStatus,
    RuntimeActionRetryEligibility,
    RuntimeActionRiskProfile,
    RuntimeActionSchemaReference,
    RuntimeActionSelector,
    RuntimeActionSideEffectLevel,
    RuntimeActionStatus,
    RuntimeActionVersion,
    RuntimeRegistryAuditMetadata,
    RuntimeRegistryCanonicalOrderError,
    RuntimeRegistryClassificationError,
    RuntimeRegistryContractVersion,
    RuntimeRegistryLifecycleError,
    RuntimeRegistryRequirementError,
    RuntimeRegistryResolutionError,
    RuntimeRegistryRevisionError,
    RuntimeRegistryScopeError,
    RuntimeRegistrySnapshotEntry,
    RuntimeRegistrySnapshotReference,
    RuntimeSpecializedPermitRequirement,
    resolve_runtime_action,
    validate_runtime_action_definition,
    validate_runtime_action_resolution_decision,
    validate_runtime_registry_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 8, 2, 12, tzinfo=UTC)


def uid(value: int) -> UUID:
    return UUID(int=value)


def definition(**updates) -> RuntimeActionDefinition:
    values = dict(
        identity=RuntimeActionIdentity(
            action_definition_id="action-definition-1",
            action="publish-policy",
            action_version="action-v1",
        ),
        version=RuntimeActionVersion(
            action_version="action-v1",
            action_contract_version="contract-v1",
            action_schema_version="schema-v1",
        ),
        capabilities=(RuntimeActionCapability.PUBLISH,),
        selectors=RuntimeActionSelector(
            resource_reference="resource-1",
            purpose="approved-policy-publication",
            execution_environment=RuntimeExecutionEnvironment.EXTERNAL,
            destination_reference="destination-1",
            model_id="model-1",
            provider_id="provider-1",
            tool_id="tool-1",
            connector_id="connector-1",
        ),
        risk_profile=RuntimeActionRiskProfile(
            risk_level=RuntimeRiskLevel.HIGH,
            side_effect_level=RuntimeActionSideEffectLevel.PUBLICATION,
            side_effect_level_reference="side-effect-policy-level-1",
            side_effect_policy_revision=7,
        ),
        input_schema=RuntimeActionSchemaReference(
            schema_reference="input-schema-1",
            schema_version="schema-v1",
            schema_digest_reference="input-digest-1",
        ),
        output_schema=RuntimeActionSchemaReference(
            schema_reference="output-schema-1",
            schema_version="schema-v1",
            schema_digest_reference="output-digest-1",
        ),
        permit_requirement=RuntimeActionPermitRequirement(
            permit_required=True,
            permit_source_types=(RuntimePermitSourceType.ZERO_TRUST,),
            specialized_requirements=(
                RuntimeSpecializedPermitRequirement(
                    permit_source_type=RuntimePermitSourceType.ZERO_TRUST,
                    permit_type_reference="publication-permit",
                    permit_policy_revision=8,
                ),
            ),
        ),
        destination_requirement=RuntimeActionDestinationRequirement(
            destination_required=True,
            destination_policy_reference="destination-policy-1",
        ),
        idempotency_requirement=RuntimeActionIdempotencyRequirement(
            idempotency_required=True,
            idempotency_policy_reference="idempotency-policy-1",
        ),
        retry_eligibility=RuntimeActionRetryEligibility(
            retry_eligible=False,
            maximum_attempt_count=1,
        ),
        compensation_eligibility=RuntimeActionCompensationEligibility(
            compensation_eligible=False
        ),
        adapter=RuntimeActionAdapterReference(
            adapter_reference="adapter-1",
            adapter_contract_version="adapter-v1",
            adapter_configuration_reference="adapter-config-1",
        ),
        tenant_id=uid(1),
        organization_id=uid(2),
        classification=DataClassification.CONFIDENTIAL,
        root_lineage_id=uid(3),
        root_lineage_digest_reference="lineage-digest-1",
        definition_digest_reference="definition-digest-1",
        created_at=NOW,
    )
    values.update(updates)
    return RuntimeActionDefinition(**values)


def entry(**updates) -> RuntimeRegistrySnapshotEntry:
    values = dict(
        runtime_registry_snapshot_entry_id=uid(4),
        action_definition=definition(),
        status=RuntimeActionStatus.ACTIVE,
        registry_revision=9,
        recorded_at=NOW + timedelta(minutes=1),
    )
    values.update(updates)
    return RuntimeRegistrySnapshotEntry(**values)


def snapshot(**updates) -> RuntimeActionRegistrySnapshot:
    values = dict(
        runtime_registry_snapshot_id=uid(5),
        contract_version=RuntimeRegistryContractVersion(
            runtime_registry_version="registry-v1",
            runtime_registry_contract_version="contract-v1",
            runtime_registry_schema_version="schema-v1",
        ),
        registry_revision=9,
        entries=(entry(),),
        tenant_id=uid(1),
        organization_id=uid(2),
        classification=DataClassification.CONFIDENTIAL,
        root_lineage_id=uid(3),
        root_lineage_digest_reference="lineage-digest-1",
        snapshot_digest_reference="snapshot-digest-1",
        audit_metadata=RuntimeRegistryAuditMetadata(
            definition_count=1,
            active_count=1,
            disabled_count=0,
            retired_count=0,
            invalidated_count=0,
            audit_digest_reference="audit-digest-1",
        ),
        created_at=NOW + timedelta(minutes=2),
    )
    values.update(updates)
    return RuntimeActionRegistrySnapshot(**values)


def reference(
    item: RuntimeActionRegistrySnapshot | None = None,
) -> RuntimeRegistrySnapshotReference:
    item = item or snapshot()
    return RuntimeRegistrySnapshotReference(
        runtime_registry_snapshot_id=item.runtime_registry_snapshot_id,
        registry_revision=item.registry_revision,
        snapshot_digest_reference=item.snapshot_digest_reference,
        tenant_id=item.tenant_id,
        organization_id=item.organization_id,
        classification=item.classification,
    )


def resolution_request(item: RuntimeActionRegistrySnapshot | None = None, **updates):
    item = item or snapshot()
    action = item.entries[0].action_definition
    values = dict(
        runtime_action_resolution_request_id=uid(6),
        snapshot_reference=reference(item),
        action_identity=action.identity,
        selectors=action.selectors,
        risk_level=action.risk_profile.risk_level,
        side_effect_level_reference=action.risk_profile.side_effect_level_reference,
        input_schema_reference=action.input_schema.schema_reference,
        output_schema_reference=action.output_schema.schema_reference,
        adapter_reference=action.adapter.adapter_reference,
        tenant_id=item.tenant_id,
        organization_id=item.organization_id,
        classification=item.classification,
        root_lineage_id=item.root_lineage_id,
        root_lineage_digest_reference=item.root_lineage_digest_reference,
        requested_at=item.created_at + timedelta(minutes=1),
    )
    values.update(updates)
    return RuntimeActionResolutionRequest(**values)


def test_definition_is_strict_frozen_extra_forbidden_and_timezone_aware() -> None:
    item = definition()
    with pytest.raises(ValidationError):
        item.action_definition_id = "changed"
    with pytest.raises(ValidationError):
        definition(created_at=NOW.replace(tzinfo=None))
    with pytest.raises(ValidationError):
        RuntimeActionIdentity(
            action_definition_id="a", action="read", action_version="v1", extra="no"
        )


def test_all_ten_side_effect_levels_are_closed() -> None:
    assert len(RuntimeActionSideEffectLevel) == 10


def test_capabilities_and_permits_require_canonical_order() -> None:
    with pytest.raises(ValidationError):
        definition(capabilities=(RuntimeActionCapability.WRITE, RuntimeActionCapability.READ))
    with pytest.raises(ValidationError):
        RuntimeActionPermitRequirement(
            permit_required=True,
            permit_source_types=(
                RuntimePermitSourceType.ZERO_TRUST,
                RuntimePermitSourceType.ZERO_TRUST,
            ),
        )


def test_governed_external_side_effect_requirements_fail_closed() -> None:
    no_permit = definition(
        permit_requirement=RuntimeActionPermitRequirement(permit_required=False)
    )
    with pytest.raises(RuntimeRegistryRequirementError):
        validate_runtime_action_definition(no_permit)
    no_destination = definition(
        destination_requirement=RuntimeActionDestinationRequirement(destination_required=False)
    )
    with pytest.raises(RuntimeRegistryRequirementError):
        validate_runtime_action_definition(no_destination)
    with pytest.raises(RuntimeRegistryRequirementError):
        validate_runtime_action_definition(
            definition(
                retry_eligibility=RuntimeActionRetryEligibility(
                    retry_eligible=True,
                    maximum_attempt_count=2,
                    retry_policy_reference="retry-policy-1",
                )
            )
        )


def test_snapshot_scope_revision_classification_counts_and_order_fail_closed() -> None:
    item = snapshot()
    assert validate_runtime_registry_snapshot(item) is item
    with pytest.raises(RuntimeRegistryRevisionError):
        validate_runtime_registry_snapshot(snapshot(entries=(entry(registry_revision=10),)))
    with pytest.raises(RuntimeRegistryScopeError):
        validate_runtime_registry_snapshot(
            snapshot(entries=(entry(action_definition=definition(tenant_id=uid(99))),))
        )
    with pytest.raises(RuntimeRegistryClassificationError):
        validate_runtime_registry_snapshot(
            snapshot(classification=DataClassification.INTERNAL)
        )
    with pytest.raises(RuntimeRegistryLifecycleError):
        validate_runtime_registry_snapshot(
            snapshot(
                audit_metadata=RuntimeRegistryAuditMetadata(
                    definition_count=0,
                    active_count=0,
                    disabled_count=0,
                    retired_count=0,
                    invalidated_count=0,
                    audit_digest_reference="audit-digest-1",
                )
            )
        )
    second = entry(
        runtime_registry_snapshot_entry_id=uid(3),
        action_definition=definition(
            identity=RuntimeActionIdentity(
                action_definition_id="action-definition-0",
                action="a-action",
                action_version="action-v1",
            )
        ),
    )
    with pytest.raises(RuntimeRegistryCanonicalOrderError):
        validate_runtime_registry_snapshot(
            snapshot(
                entries=(entry(), second),
                audit_metadata=RuntimeRegistryAuditMetadata(
                    definition_count=2,
                    active_count=2,
                    disabled_count=0,
                    retired_count=0,
                    invalidated_count=0,
                    audit_digest_reference="audit-digest-2",
                ),
            )
        )


def test_invalidation_requires_distinct_original_entry_in_same_snapshot() -> None:
    original = entry(runtime_registry_snapshot_entry_id=uid(4), registry_revision=8)
    invalidated = entry(
        runtime_registry_snapshot_entry_id=uid(7),
        status=RuntimeActionStatus.INVALIDATED,
        status_reason_reference="invalidated-reason-1",
        original_snapshot_entry_id=original.runtime_registry_snapshot_entry_id,
        invalidation_reference="invalidation-record-1",
    )
    item = snapshot(
        entries=(original, invalidated),
        audit_metadata=RuntimeRegistryAuditMetadata(
            definition_count=2,
            active_count=1,
            disabled_count=0,
            retired_count=0,
            invalidated_count=1,
            audit_digest_reference="audit-digest-2",
        ),
    )
    assert validate_runtime_registry_snapshot(item) is item
    with pytest.raises(RuntimeRegistryLifecycleError):
        validate_runtime_registry_snapshot(snapshot(entries=(invalidated,)))


def test_snapshot_rejects_multiple_active_entries_for_one_identity() -> None:
    duplicate = entry(runtime_registry_snapshot_entry_id=uid(10))
    with pytest.raises(RuntimeRegistryLifecycleError):
        validate_runtime_registry_snapshot(
            snapshot(
                entries=(entry(), duplicate),
                audit_metadata=RuntimeRegistryAuditMetadata(
                    definition_count=2,
                    active_count=2,
                    disabled_count=0,
                    retired_count=0,
                    invalidated_count=0,
                    audit_digest_reference="audit-digest-duplicate",
                ),
            )
        )


def test_resolution_is_exact_and_active() -> None:
    item = snapshot()
    request = resolution_request(item)
    assert resolve_runtime_action(request, item) == item.entries[0]
    with pytest.raises(RuntimeRegistryResolutionError):
        resolve_runtime_action(
            resolution_request(item, adapter_reference="substituted-adapter"), item
        )
    inactive = snapshot(
        entries=(
            entry(status=RuntimeActionStatus.DISABLED, status_reason_reference="disabled-1"),
        ),
        audit_metadata=RuntimeRegistryAuditMetadata(
            definition_count=1,
            active_count=0,
            disabled_count=1,
            retired_count=0,
            invalidated_count=0,
            audit_digest_reference="audit-digest-disabled",
        ),
    )
    with pytest.raises(RuntimeRegistryLifecycleError):
        resolve_runtime_action(resolution_request(inactive), inactive)


def test_resolution_decision_is_caller_supplied_evidence_not_authority() -> None:
    item = snapshot()
    request = resolution_request(item)
    decision = RuntimeActionResolutionDecision(
        runtime_action_resolution_decision_id=uid(8),
        runtime_action_resolution_request_id=request.runtime_action_resolution_request_id,
        snapshot_reference=request.snapshot_reference,
        decision_status=RuntimeActionResolutionStatus.RESOLVED,
        reason_codes=(RuntimeActionResolutionReasonCode.CALLER_SUPPLIED,),
        resolved_snapshot_entry_id=item.entries[0].runtime_registry_snapshot_entry_id,
        tenant_id=request.tenant_id,
        organization_id=request.organization_id,
        classification=request.classification,
        root_lineage_id=request.root_lineage_id,
        root_lineage_digest_reference=request.root_lineage_digest_reference,
        decided_at=request.requested_at + timedelta(minutes=1),
    )
    assert validate_runtime_action_resolution_decision(decision, request, item) is decision


def test_cp2_action_reference_is_field_compatible_without_registry_import() -> None:
    item = snapshot()
    request = resolution_request(item)
    action = item.entries[0].action_definition
    cp2 = ExecutionActionReference(
        execution_action_reference_id=uid(9),
        action_definition_id=action.identity.action_definition_id,
        action_version=action.identity.action_version,
        registry_revision=item.registry_revision,
        resource_reference=action.selectors.resource_reference,
        action=action.identity.action,
        purpose=action.selectors.purpose,
        risk_level=action.risk_profile.risk_level,
        side_effect_level_reference=action.risk_profile.side_effect_level_reference,
        input_schema_reference=action.input_schema.schema_reference,
        output_schema_reference=action.output_schema.schema_reference,
        adapter_reference=action.adapter.adapter_reference,
        execution_environment=action.selectors.execution_environment,
        destination_reference=action.selectors.destination_reference,
        model_id=action.selectors.model_id,
        provider_id=action.selectors.provider_id,
        tool_id=action.selectors.tool_id,
        connector_id=action.selectors.connector_id,
        tenant_id=item.tenant_id,
        organization_id=item.organization_id,
        classification=item.classification,
        created_at=request.requested_at,
    )
    assert cp2.action_definition_id == request.action_identity.action_definition_id
    registry_sources = tuple((ROOT / "app" / "runtime" / "registry").glob("*.py"))
    assert all(
        "app.runtime.planning" not in source.read_text(encoding="utf-8")
        and "app.runtime.state" not in source.read_text(encoding="utf-8")
        for source in registry_sources
    )


def test_registry_contains_no_executable_or_infrastructure_surface() -> None:
    forbidden = (
        "FastAPI",
        "sqlalchemy",
        "redis",
        "subprocess",
        "importlib",
        "openai",
        "anthropic",
        "requests",
        "httpx",
        "callback",
    )
    for source in (ROOT / "app" / "runtime" / "registry").glob("*.py"):
        text = source.read_text(encoding="utf-8")
        assert all(value not in text for value in forbidden)
