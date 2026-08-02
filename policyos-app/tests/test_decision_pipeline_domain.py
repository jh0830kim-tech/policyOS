"""Sprint 14 CP5 immutable Decision Pipeline domain tests."""

import ast
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.decision_pipeline import (
    DecisionPipeline,
    DecisionPipelineAuditMetadata,
    DecisionPipelineAuditMetadataError,
    DecisionPipelineClassificationError,
    DecisionPipelineLineageError,
    DecisionPipelineLineageReference,
    DecisionPipelineOrderingError,
    DecisionPipelineOrganizationError,
    DecisionPipelinePackageBinding,
    DecisionPipelinePackageBindingError,
    DecisionPipelineProvenanceReference,
    DecisionPipelineReasonCode,
    DecisionPipelineRequest,
    DecisionPipelineStage,
    DecisionPipelineStageError,
    DecisionPipelineStageRecord,
    DecisionPipelineStageStatus,
    DecisionPipelineStatus,
    DecisionPipelineTenantError,
    DecisionPipelineVersion,
    DecisionPipelineVersionError,
    DecisionReleaseGateError,
    DecisionReleaseGateRecord,
    DecisionReleaseGateStatus,
    DuplicateDecisionPipelineReferenceError,
    OrphanDecisionPipelineReferenceError,
    build_decision_pipeline,
    validate_decision_pipeline,
    validate_decision_pipeline_audit_metadata,
    validate_decision_pipeline_lineage_reference,
    validate_decision_pipeline_package_binding,
    validate_decision_pipeline_provenance_reference,
    validate_decision_pipeline_stage_record,
    validate_decision_release_gate_record,
)
from app.decisions import DecisionPackage
from tests.test_decision_package_domain import package_values
from tests.test_evaluation_planner import uid

ROOT = Path(__file__).resolve().parents[1]


def pipeline_values(*, audit: bool = False):
    package_data, _ = package_values()
    package = DecisionPackage(**package_data)

    pipeline_id = uid(97100)
    review_ids = (
        package.review_summary.unresolved_review_requirement_ids
    )

    binding = DecisionPipelinePackageBinding(
        decision_pipeline_package_binding_id=uid(97101),
        decision_package_id=package.decision_package_id,
        decision_package_version=package.package_version,
        package_status=package.package_status,
        disposition_type=package.disposition_type,
        unresolved_review_requirement_ids=review_ids,
        separate_approval_required=(
            package.review_summary.separate_approval_required
        ),
        external_authorization_required=(
            package.review_summary.external_authorization_required
        ),
        publication_authorization_required=(
            package.review_summary.publication_authorization_required
        ),
        external_transmission_authorization_required=(
            package.review_summary.external_transmission_authorization_required
        ),
        tenant_id=package.tenant_id,
        organization_id=package.organization_id,
        classification=package.classification,
        policy_revision=package.policy_revision,
        authorization_revision=package.authorization_revision,
        registry_revision=package.registry_revision,
        lineage_reference_ids=(
            package.lineage_references[
                0
            ].decision_package_lineage_reference_id,
        ),
        provenance_reference_ids=(
            package.provenance_references[
                0
            ].decision_package_provenance_reference_id,
        ),
        bound_at=package.recorded_at,
    )

    stage = DecisionPipelineStageRecord(
        decision_pipeline_stage_record_id=uid(97102),
        decision_pipeline_id=pipeline_id,
        stage=DecisionPipelineStage.ASSEMBLY,
        stage_sequence=1,
        stage_status=DecisionPipelineStageStatus.RECORDED,
        package_binding_ids=(
            binding.decision_pipeline_package_binding_id,
        ),
        review_requirement_ids=review_ids,
        policy_revision=package.policy_revision,
        authorization_revision=package.authorization_revision,
        registry_revision=package.registry_revision,
        classification=package.classification,
        lineage_id=package.root_lineage_id,
        lineage_digest_reference=(
            package.root_lineage_digest_reference
        ),
        reason_codes=(
            DecisionPipelineReasonCode.CALLER_SUPPLIED,
        ),
        recorded_at=package.recorded_at + timedelta(seconds=1),
    )

    gate = DecisionReleaseGateRecord(
        decision_release_gate_record_id=uid(97103),
        decision_pipeline_id=pipeline_id,
        release_gate_status=(
            DecisionReleaseGateStatus.REVIEW_REQUIRED
        ),
        decision_package_ids=(package.decision_package_id,),
        unresolved_review_requirement_ids=review_ids,
        blocking_security_reference_ids=(uid(97120),),
        blocking_legal_reference_ids=(uid(97121),),
        blocking_policy_reference_ids=(uid(97122),),
        separate_approval_required=(
            binding.separate_approval_required
        ),
        external_authorization_required=(
            binding.external_authorization_required
        ),
        publication_authorization_required=(
            binding.publication_authorization_required
        ),
        external_transmission_authorization_required=(
            binding.external_transmission_authorization_required
        ),
        release_condition_reference_ids=(uid(97123),),
        reason_codes=(
            DecisionPipelineReasonCode.CALLER_SUPPLIED,
        ),
        actor_id=uid(97124),
        agent_instance_id=uid(97125),
        tenant_id=package.tenant_id,
        organization_id=package.organization_id,
        classification=package.classification,
        root_lineage_id=package.root_lineage_id,
        root_lineage_digest_reference=(
            package.root_lineage_digest_reference
        ),
        policy_revision=package.policy_revision,
        authorization_revision=package.authorization_revision,
        registry_revision=package.registry_revision,
        recorded_at=package.recorded_at + timedelta(seconds=2),
    )

    lineage = DecisionPipelineLineageReference(
        decision_pipeline_lineage_reference_id=uid(97104),
        decision_pipeline_id=pipeline_id,
        root_lineage_id=package.root_lineage_id,
        root_lineage_digest_reference=(
            package.root_lineage_digest_reference
        ),
        decision_package_ids=(package.decision_package_id,),
        package_binding_ids=(
            binding.decision_pipeline_package_binding_id,
        ),
        stage_record_ids=(
            stage.decision_pipeline_stage_record_id,
        ),
        release_gate_record_ids=(
            gate.decision_release_gate_record_id,
        ),
        lineage_schema_version=(
            "decision-pipeline-lineage-schema-v1"
        ),
        created_at=gate.recorded_at,
    )

    provenance = DecisionPipelineProvenanceReference(
        decision_pipeline_provenance_reference_id=uid(97105),
        decision_pipeline_id=pipeline_id,
        decision_package_ids=(package.decision_package_id,),
        policy_revision=package.policy_revision,
        authorization_revision=package.authorization_revision,
        registry_revision=package.registry_revision,
        provenance_schema_version=(
            "decision-pipeline-provenance-schema-v1"
        ),
        recorded_at=gate.recorded_at,
    )

    version = DecisionPipelineVersion(
        decision_pipeline_version="decision-pipeline-v1",
        decision_pipeline_contract_version="contract-v1",
        decision_pipeline_schema_version=(
            "decision-pipeline-schema-v1"
        ),
    )

    recorded_at = gate.recorded_at + timedelta(seconds=1)

    values = {
        "decision_pipeline_id": pipeline_id,
        "pipeline_version": version,
        "pipeline_status": DecisionPipelineStatus.ASSEMBLED,
        "current_stage": DecisionPipelineStage.ASSEMBLY,
        "package_bindings": (binding,),
        "stage_records": (stage,),
        "release_gate_records": (gate,),
        "lineage_references": (lineage,),
        "provenance_references": (provenance,),
        "reason_codes": (
            DecisionPipelineReasonCode.CALLER_SUPPLIED,
        ),
        "actor_id": uid(97106),
        "agent_instance_id": uid(97107),
        "on_behalf_of_user_id": uid(97108),
        "tenant_id": package.tenant_id,
        "organization_id": package.organization_id,
        "classification": package.classification,
        "root_lineage_id": package.root_lineage_id,
        "root_lineage_digest_reference": (
            package.root_lineage_digest_reference
        ),
        "policy_revision": package.policy_revision,
        "authorization_revision": (
            package.authorization_revision
        ),
        "registry_revision": package.registry_revision,
        "recorded_at": recorded_at,
    }

    if audit:
        values["audit_metadata"] = (
            DecisionPipelineAuditMetadata(
                decision_pipeline_id=pipeline_id,
                pipeline_version=version,
                package_binding_count=1,
                stage_record_count=1,
                release_gate_record_count=1,
                unresolved_review_count=1,
                blocking_security_reference_count=1,
                blocking_legal_reference_count=1,
                blocking_policy_reference_count=1,
                release_condition_reference_count=1,
                lineage_reference_count=1,
                provenance_reference_count=1,
                tenant_id=package.tenant_id,
                organization_id=package.organization_id,
                classification=package.classification,
                policy_revision=package.policy_revision,
                registry_revision=package.registry_revision,
                created_at=recorded_at,
            )
        )

    return values, package


def test_contracts_are_strict_frozen_extra_forbidden_and_caller_supplied():
    values, _ = pipeline_values()
    pipeline = DecisionPipeline(**values)

    assert pipeline.decision_pipeline_id == uid(97100)
    assert pipeline.pipeline_version is values["pipeline_version"]
    assert pipeline.actor_id == uid(97106)

    with pytest.raises(ValidationError):
        pipeline.actor_id = uid(97901)

    with pytest.raises(ValidationError):
        DecisionPipeline(**values, extra="forbidden")

    with pytest.raises(ValidationError):
        DecisionPipeline(
            **(values | {"policy_revision": "1"})
        )

    with pytest.raises(ValidationError):
        DecisionPipeline(
            **(
                values
                | {
                    "recorded_at": values[
                        "recorded_at"
                    ].replace(tzinfo=None)
                }
            )
        )


@pytest.mark.parametrize(
    "field,value,error",
    (
        (
            "decision_package_id",
            uid(97902),
            DecisionPipelinePackageBindingError,
        ),
        (
            "package_status",
            None,
            DecisionPipelinePackageBindingError,
        ),
        (
            "unresolved_review_requirement_ids",
            (),
            DecisionPipelinePackageBindingError,
        ),
        (
            "tenant_id",
            uid(97903),
            DecisionPipelineTenantError,
        ),
        (
            "organization_id",
            uid(97904),
            DecisionPipelineOrganizationError,
        ),
        (
            "classification",
            DataClassification.PUBLIC,
            DecisionPipelineClassificationError,
        ),
        (
            "policy_revision",
            2,
            DecisionPipelineVersionError,
        ),
        (
            "lineage_reference_ids",
            (uid(97905),),
            OrphanDecisionPipelineReferenceError,
        ),
    ),
)
def test_package_binding_is_exact(field, value, error):
    values, package = pipeline_values()

    binding = values["package_bindings"][0].model_copy(
        update={field: value}
    )

    with pytest.raises(error):
        validate_decision_pipeline_package_binding(
            binding,
            package,
        )


def test_stage_sequence_binding_and_lineage_are_exact():
    values, package = pipeline_values()
    pipeline = DecisionPipeline(**values)
    stage = pipeline.stage_records[0]

    assert (
        validate_decision_pipeline_stage_record(
            stage,
            pipeline.decision_pipeline_id,
            stage.package_binding_ids,
            stage.review_requirement_ids,
            pipeline.root_lineage_id,
            pipeline.root_lineage_digest_reference,
        )
        is stage
    )

    invalid_stage = stage.model_copy(
        update={"stage_sequence": 2}
    )

    with pytest.raises(DecisionPipelineStageError):
        validate_decision_pipeline(
            pipeline.model_copy(
                update={"stage_records": (invalid_stage,)}
            ),
            (package,),
        )


@pytest.mark.parametrize(
    "status",
    tuple(DecisionReleaseGateStatus),
)
def test_release_gate_status_is_inert_caller_metadata(status):
    values, _ = pipeline_values()
    pipeline = DecisionPipeline(**values)

    gate = pipeline.release_gate_records[0].model_copy(
        update={"release_gate_status": status}
    )

    assert (
        validate_decision_release_gate_record(
            gate,
            pipeline,
            gate.decision_package_ids,
            gate.unresolved_review_requirement_ids,
        )
        is gate
    )

    assert gate.separate_approval_required is True
    assert gate.external_authorization_required is True


def test_release_gate_rejects_review_scope_and_lineage_substitution():
    values, _ = pipeline_values()
    pipeline = DecisionPipeline(**values)
    gate = pipeline.release_gate_records[0]

    with pytest.raises(DecisionReleaseGateError):
        validate_decision_release_gate_record(
            gate,
            pipeline,
            gate.decision_package_ids,
            (),
        )

    with pytest.raises(DecisionPipelineTenantError):
        validate_decision_release_gate_record(
            gate.model_copy(
                update={"tenant_id": uid(97906)}
            ),
            pipeline,
            gate.decision_package_ids,
            gate.unresolved_review_requirement_ids,
        )

    with pytest.raises(DecisionReleaseGateError):
        validate_decision_release_gate_record(
            gate.model_copy(
                update={
                    "root_lineage_id": uid(97907)
                }
            ),
            pipeline,
            gate.decision_package_ids,
            gate.unresolved_review_requirement_ids,
        )


def test_lineage_and_provenance_preserve_exact_references():
    values, _ = pipeline_values()
    pipeline = DecisionPipeline(**values)

    lineage = pipeline.lineage_references[0]
    provenance = pipeline.provenance_references[0]

    assert (
        validate_decision_pipeline_lineage_reference(
            lineage,
            pipeline,
            lineage.decision_package_ids,
            lineage.package_binding_ids,
            lineage.stage_record_ids,
            lineage.release_gate_record_ids,
        )
        is lineage
    )

    assert (
        validate_decision_pipeline_provenance_reference(
            provenance,
            pipeline,
            provenance.decision_package_ids,
        )
        is provenance
    )

    self_parent = lineage.model_copy(
        update={
            "parent_decision_pipeline_ids": (
                pipeline.decision_pipeline_id,
            )
        }
    )

    with pytest.raises(DecisionPipelineLineageError):
        validate_decision_pipeline_lineage_reference(
            self_parent,
            pipeline,
            lineage.decision_package_ids,
            lineage.package_binding_ids,
            lineage.stage_record_ids,
            lineage.release_gate_record_ids,
        )


def test_builder_returns_new_valid_pipeline_without_progression_or_mutation():
    values, package = pipeline_values(audit=True)
    pipeline = DecisionPipeline(**values)

    request = DecisionPipelineRequest(
        pipeline=pipeline,
        decision_packages=(package,),
    )
    before = request.model_dump()

    result = build_decision_pipeline(request)

    assert result == pipeline
    assert result is not pipeline
    assert result.current_stage is DecisionPipelineStage.ASSEMBLY
    assert request.model_dump() == before


@pytest.mark.parametrize(
    "status,reason,updates",
    (
        (
            DecisionPipelineStatus.ACTIVE,
            DecisionPipelineReasonCode.CALLER_SUPPLIED,
            {},
        ),
        (
            DecisionPipelineStatus.COMPLETED,
            DecisionPipelineReasonCode.CALLER_SUPPLIED,
            {},
        ),
        (
            DecisionPipelineStatus.UNAVAILABLE,
            DecisionPipelineReasonCode.INPUT_UNAVAILABLE,
            {},
        ),
        (
            DecisionPipelineStatus.CANCELLED,
            DecisionPipelineReasonCode.PIPELINE_CANCELLED,
            {},
        ),
        (
            DecisionPipelineStatus.INVALIDATED,
            DecisionPipelineReasonCode.PIPELINE_INVALIDATED,
            {
                "original_decision_pipeline_id": uid(97099),
                "invalidation_reference": (
                    "invalidation://caller/1"
                ),
            },
        ),
    ),
)
def test_pipeline_lifecycle_is_metadata_only(
    status,
    reason,
    updates,
):
    values, _ = pipeline_values()

    values.update(
        pipeline_status=status,
        reason_codes=(reason,),
        **updates,
    )

    pipeline = DecisionPipeline(**values)

    assert pipeline.pipeline_status is status
    assert pipeline.reason_codes == (reason,)


def test_audit_counts_are_exact_and_boolean_counts_fail():
    values, package = pipeline_values(audit=True)
    pipeline = DecisionPipeline(**values)

    assert (
        validate_decision_pipeline_audit_metadata(
            pipeline.audit_metadata
        )
        is pipeline.audit_metadata
    )

    assert (
        validate_decision_pipeline(
            pipeline,
            (package,),
        )
        is pipeline
    )

    with pytest.raises(ValidationError):
        DecisionPipelineAuditMetadata(
            **(
                pipeline.audit_metadata.model_dump()
                | {"stage_record_count": True}
            )
        )

    mismatch = pipeline.audit_metadata.model_copy(
        update={"stage_record_count": 2}
    )

    with pytest.raises(
        DecisionPipelineAuditMetadataError
    ):
        validate_decision_pipeline(
            pipeline.model_copy(
                update={"audit_metadata": mismatch}
            ),
            (package,),
        )


def test_ordering_duplicate_and_orphan_rejection_is_fail_closed():
    values, package = pipeline_values()
    pipeline = DecisionPipeline(**values)

    with pytest.raises(
        DuplicateDecisionPipelineReferenceError
    ):
        validate_decision_pipeline(
            pipeline.model_copy(
                update={
                    "package_bindings": (
                        pipeline.package_bindings * 2
                    )
                }
            ),
            (package,),
        )

    original_gate = pipeline.release_gate_records[0]

    earlier_gate = original_gate.model_copy(
        update={
            "decision_release_gate_record_id": uid(97001),
            "recorded_at": (
                original_gate.recorded_at
                - timedelta(microseconds=1)
            ),
        }
    )

    noncanonical_pipeline = pipeline.model_copy(
        update={
            "release_gate_records": (
                original_gate,
                earlier_gate,
            )
        }
    )

    with pytest.raises(DecisionPipelineOrderingError):
        validate_decision_pipeline(
            noncanonical_pipeline,
            (package,),
        )

    with pytest.raises(
        OrphanDecisionPipelineReferenceError
    ):
        validate_decision_pipeline(
            pipeline,
            (),
        )


def test_cp5_production_has_no_runtime_or_io_boundary():
    forbidden_imports = {
        "asyncio",
        "httpx",
        "requests",
        "socket",
        "subprocess",
        "sqlalchemy",
        "redis",
        "fastapi",
        "opentelemetry",
    }

    forbidden_calls = {
        "now",
        "utcnow",
        "time",
        "uuid4",
        "open",
        "connect",
        "execute",
        "deploy",
        "publish",
        "send",
        "commit",
    }

    for path in (
        ROOT / "app" / "decision_pipeline"
    ).glob("*.py"):
        tree = ast.parse(
            path.read_text(encoding="utf-8")
        )

        for node in ast.walk(tree):
            if isinstance(
                node,
                (ast.Import, ast.ImportFrom),
            ):
                names = (
                    [
                        alias.name
                        for alias in node.names
                    ]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )

                imported_roots = {
                    name.split(".")[0].lower()
                    for name in names
                }

                assert not (
                    imported_roots & forbidden_imports
                )

            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(
                        node.func,
                        ast.Name,
                    )
                    else node.func.attr
                    if isinstance(
                        node.func,
                        ast.Attribute,
                    )
                    else ""
                )

                assert name not in forbidden_calls