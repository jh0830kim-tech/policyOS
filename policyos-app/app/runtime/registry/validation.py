"""Pure fail-closed validation for immutable runtime registry snapshots."""

from app.runtime.registry._base import canonical, not_lower
from app.runtime.registry.domain import (
    RuntimeActionDefinition,
    RuntimeActionRegistrySnapshot,
    RuntimeActionResolutionDecision,
    RuntimeActionResolutionRequest,
    RuntimeActionResolutionStatus,
    RuntimeActionSideEffectLevel,
    RuntimeActionStatus,
    RuntimeRegistrySnapshotEntry,
    RuntimeRegistrySnapshotReference,
)
from app.runtime.registry.errors import (
    RuntimeRegistryCanonicalOrderError,
    RuntimeRegistryClassificationError,
    RuntimeRegistryLifecycleError,
    RuntimeRegistryRequirementError,
    RuntimeRegistryResolutionError,
    RuntimeRegistryRevisionError,
    RuntimeRegistryScopeError,
    RuntimeRegistryTimestampError,
)

GOVERNED_SIDE_EFFECTS = frozenset(
    level
    for level in RuntimeActionSideEffectLevel
    if level not in {RuntimeActionSideEffectLevel.NONE, RuntimeActionSideEffectLevel.READ_ONLY}
)
EXTERNAL_SIDE_EFFECTS = frozenset(
    {
        RuntimeActionSideEffectLevel.EXTERNAL_WRITE,
        RuntimeActionSideEffectLevel.PUBLICATION,
        RuntimeActionSideEffectLevel.EXTERNAL_TRANSMISSION,
        RuntimeActionSideEffectLevel.DEPLOYMENT,
        RuntimeActionSideEffectLevel.DESTRUCTIVE,
        RuntimeActionSideEffectLevel.SECURITY_CONTROL,
        RuntimeActionSideEffectLevel.QUARANTINE_ACTION,
    }
)
NON_RETRYABLE_SIDE_EFFECTS = frozenset(
    {
        RuntimeActionSideEffectLevel.PUBLICATION,
        RuntimeActionSideEffectLevel.DEPLOYMENT,
        RuntimeActionSideEffectLevel.DESTRUCTIVE,
        RuntimeActionSideEffectLevel.SECURITY_CONTROL,
        RuntimeActionSideEffectLevel.QUARANTINE_ACTION,
    }
)


def validate_runtime_action_definition(
    definition: RuntimeActionDefinition,
) -> RuntimeActionDefinition:
    side_effect = definition.risk_profile.side_effect_level
    if side_effect in GOVERNED_SIDE_EFFECTS and not definition.permit_requirement.permit_required:
        raise RuntimeRegistryRequirementError("governed side effect requires a permit")
    if side_effect in EXTERNAL_SIDE_EFFECTS:
        if not definition.destination_requirement.destination_required:
            raise RuntimeRegistryRequirementError(
                "external side effect requires destination policy"
            )
        if definition.selectors.destination_reference is None:
            raise RuntimeRegistryRequirementError(
                "external side effect requires destination selector"
            )
    if side_effect in GOVERNED_SIDE_EFFECTS and not (
        definition.idempotency_requirement.idempotency_required
    ):
        raise RuntimeRegistryRequirementError("write side effect requires idempotency policy")
    if side_effect in NON_RETRYABLE_SIDE_EFFECTS and definition.retry_eligibility.retry_eligible:
        raise RuntimeRegistryRequirementError("sensitive side effect cannot be retry eligible")
    return definition


def _entry_key(entry: RuntimeRegistrySnapshotEntry) -> tuple[str, str, str, str]:
    identity = entry.action_definition.identity
    return (
        identity.action_definition_id,
        identity.action,
        identity.action_version,
        str(entry.runtime_registry_snapshot_entry_id),
    )


def validate_runtime_registry_snapshot(
    snapshot: RuntimeActionRegistrySnapshot,
) -> RuntimeActionRegistrySnapshot:
    if not canonical(snapshot.entries, key=_entry_key):
        raise RuntimeRegistryCanonicalOrderError(
            "snapshot entries must be unique and canonically ordered"
        )
    counts = {status: 0 for status in RuntimeActionStatus}
    entries_by_id = {entry.runtime_registry_snapshot_entry_id: entry for entry in snapshot.entries}
    active_identities = tuple(
        entry.action_definition.identity
        for entry in snapshot.entries
        if entry.status is RuntimeActionStatus.ACTIVE
    )
    if len(active_identities) != len(set(active_identities)):
        raise RuntimeRegistryLifecycleError(
            "snapshot cannot contain multiple active entries for one action identity"
        )
    for entry in snapshot.entries:
        definition = validate_runtime_action_definition(entry.action_definition)
        counts[entry.status] += 1
        if entry.registry_revision > snapshot.registry_revision:
            raise RuntimeRegistryRevisionError("entry revision exceeds snapshot revision")
        if (definition.tenant_id, definition.organization_id) != (
            snapshot.tenant_id,
            snapshot.organization_id,
        ):
            raise RuntimeRegistryScopeError("action definition crosses snapshot scope")
        if definition.root_lineage_id != snapshot.root_lineage_id:
            raise RuntimeRegistryScopeError("action definition crosses snapshot lineage")
        if not not_lower(snapshot.classification, definition.classification):
            raise RuntimeRegistryClassificationError(
                "snapshot classification is below action definition"
            )
        if entry.recorded_at < definition.created_at or snapshot.created_at < entry.recorded_at:
            raise RuntimeRegistryTimestampError("registry timestamps are out of order")
        if entry.status is RuntimeActionStatus.INVALIDATED:
            original = entries_by_id.get(entry.original_snapshot_entry_id)
            if original is None:
                raise RuntimeRegistryLifecycleError(
                    "invalidated entry requires original entry in the same snapshot"
                )
            if original.action_definition.identity != definition.identity:
                raise RuntimeRegistryLifecycleError(
                    "invalidated entry and original must bind the same action identity"
                )
            if entry.registry_revision != snapshot.registry_revision:
                raise RuntimeRegistryRevisionError(
                    "invalidation must be recorded at the snapshot revision"
                )
            if original.registry_revision >= entry.registry_revision:
                raise RuntimeRegistryRevisionError(
                    "invalidation requires an original entry from an earlier revision"
                )
    audit = snapshot.audit_metadata
    expected = (
        len(snapshot.entries),
        counts[RuntimeActionStatus.ACTIVE],
        counts[RuntimeActionStatus.DISABLED],
        counts[RuntimeActionStatus.RETIRED],
        counts[RuntimeActionStatus.INVALIDATED],
    )
    actual = (
        audit.definition_count,
        audit.active_count,
        audit.disabled_count,
        audit.retired_count,
        audit.invalidated_count,
    )
    if actual != expected:
        raise RuntimeRegistryLifecycleError("registry audit counts differ from snapshot entries")
    return snapshot


def validate_runtime_registry_snapshot_reference(
    reference: RuntimeRegistrySnapshotReference,
    snapshot: RuntimeActionRegistrySnapshot,
) -> RuntimeRegistrySnapshotReference:
    if (
        reference.runtime_registry_snapshot_id,
        reference.registry_revision,
        reference.snapshot_digest_reference,
        reference.tenant_id,
        reference.organization_id,
    ) != (
        snapshot.runtime_registry_snapshot_id,
        snapshot.registry_revision,
        snapshot.snapshot_digest_reference,
        snapshot.tenant_id,
        snapshot.organization_id,
    ):
        raise RuntimeRegistryRevisionError("snapshot reference is not exact")
    if not not_lower(reference.classification, snapshot.classification):
        raise RuntimeRegistryClassificationError(
            "snapshot reference classification is below snapshot"
        )
    return reference


def resolve_runtime_action(
    request: RuntimeActionResolutionRequest,
    snapshot: RuntimeActionRegistrySnapshot,
) -> RuntimeRegistrySnapshotEntry:
    validate_runtime_registry_snapshot(snapshot)
    validate_runtime_registry_snapshot_reference(request.snapshot_reference, snapshot)
    if (request.tenant_id, request.organization_id, request.root_lineage_id) != (
        snapshot.tenant_id,
        snapshot.organization_id,
        snapshot.root_lineage_id,
    ):
        raise RuntimeRegistryScopeError("resolution request crosses snapshot scope")
    if request.root_lineage_digest_reference != snapshot.root_lineage_digest_reference:
        raise RuntimeRegistryScopeError("resolution request lineage digest differs")
    if not not_lower(request.classification, snapshot.classification):
        raise RuntimeRegistryClassificationError(
            "resolution classification is below snapshot"
        )
    matches = [
        entry
        for entry in snapshot.entries
        if entry.action_definition.identity == request.action_identity
    ]
    if len(matches) != 1:
        raise RuntimeRegistryResolutionError("action identity did not resolve exactly once")
    entry = matches[0]
    if entry.status is not RuntimeActionStatus.ACTIVE:
        raise RuntimeRegistryLifecycleError("only active action may resolve")
    definition = entry.action_definition
    if (
        request.selectors,
        request.risk_level,
        request.side_effect_level_reference,
        request.input_schema_reference,
        request.output_schema_reference,
        request.adapter_reference,
    ) != (
        definition.selectors,
        definition.risk_profile.risk_level,
        definition.risk_profile.side_effect_level_reference,
        definition.input_schema.schema_reference,
        definition.output_schema.schema_reference,
        definition.adapter.adapter_reference,
    ):
        raise RuntimeRegistryResolutionError("resolution request differs from action definition")
    if request.requested_at < snapshot.created_at:
        raise RuntimeRegistryTimestampError("resolution request predates snapshot")
    return entry


def validate_runtime_action_resolution_decision(
    decision: RuntimeActionResolutionDecision,
    request: RuntimeActionResolutionRequest,
    snapshot: RuntimeActionRegistrySnapshot,
) -> RuntimeActionResolutionDecision:
    validate_runtime_registry_snapshot(snapshot)
    validate_runtime_registry_snapshot_reference(request.snapshot_reference, snapshot)
    if decision.runtime_action_resolution_request_id != (
        request.runtime_action_resolution_request_id
    ):
        raise RuntimeRegistryResolutionError("decision request reference differs")
    if decision.snapshot_reference != request.snapshot_reference:
        raise RuntimeRegistryRevisionError("decision snapshot reference differs")
    if (
        decision.tenant_id,
        decision.organization_id,
        decision.root_lineage_id,
        decision.root_lineage_digest_reference,
    ) != (
        request.tenant_id,
        request.organization_id,
        request.root_lineage_id,
        request.root_lineage_digest_reference,
    ):
        raise RuntimeRegistryScopeError("decision crosses resolution request scope")
    if not not_lower(decision.classification, request.classification):
        raise RuntimeRegistryClassificationError("decision classification is below request")
    if decision.decided_at < request.requested_at:
        raise RuntimeRegistryTimestampError("decision predates resolution request")
    if decision.decision_status is RuntimeActionResolutionStatus.RESOLVED:
        entry = resolve_runtime_action(request, snapshot)
        if decision.resolved_snapshot_entry_id != entry.runtime_registry_snapshot_entry_id:
            raise RuntimeRegistryResolutionError("decision resolved a substituted action entry")
    return decision
