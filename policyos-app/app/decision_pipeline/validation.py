"""Pure deterministic Decision Pipeline validation."""

from app.decision_pipeline.domain import (
    DecisionPipeline,
    DecisionPipelineAuditMetadata,
    DecisionPipelineLineageReference,
    DecisionPipelinePackageBinding,
    DecisionPipelineProvenanceReference,
    DecisionPipelineRequest,
    DecisionPipelineStageRecord,
    DecisionReleaseGateRecord,
)
from app.decision_pipeline.errors import (
    DecisionPipelineAuditMetadataError,
    DecisionPipelineClassificationError,
    DecisionPipelineError,
    DecisionPipelineLineageError,
    DecisionPipelineOrderingError,
    DecisionPipelineOrganizationError,
    DecisionPipelinePackageBindingError,
    DecisionPipelineProvenanceError,
    DecisionPipelineStageError,
    DecisionPipelineTenantError,
    DecisionPipelineVersionError,
    DecisionReleaseGateError,
    DuplicateDecisionPipelineReferenceError,
    OrphanDecisionPipelineReferenceError,
)
from app.decisions import DecisionPackage
from app.execution.validation import require_not_lower


def _classification(actual, required) -> None:
    try:
        require_not_lower(actual, required, field="decision pipeline classification")
    except ValueError as exc:
        raise DecisionPipelineClassificationError(
            "decision pipeline classification downgrade"
        ) from exc


def _scope(item, tenant_id, organization_id) -> None:
    if item.tenant_id != tenant_id:
        raise DecisionPipelineTenantError("decision pipeline tenant mismatch")
    if item.organization_id != organization_id:
        raise DecisionPipelineOrganizationError("decision pipeline organization mismatch")


def validate_decision_pipeline_package_binding(
    binding: DecisionPipelinePackageBinding,
    package: DecisionPackage,
) -> DecisionPipelinePackageBinding:
    if binding.decision_package_id != package.decision_package_id:
        raise DecisionPipelinePackageBindingError("decision package identity mismatch")
    if binding.decision_package_version != package.package_version:
        raise DecisionPipelineVersionError("decision package version mismatch")
    if binding.package_status is not package.package_status:
        raise DecisionPipelinePackageBindingError("decision package status mismatch")
    if binding.disposition_type is not package.disposition_type:
        raise DecisionPipelinePackageBindingError("decision disposition mismatch")
    _scope(binding, package.tenant_id, package.organization_id)
    _classification(binding.classification, package.classification)
    review = package.review_summary
    unresolved = review.unresolved_review_requirement_ids if review is not None else ()
    flags = (
        review.separate_approval_required if review is not None else False,
        review.external_authorization_required if review is not None else False,
        review.publication_authorization_required if review is not None else False,
        review.external_transmission_authorization_required if review is not None else False,
    )
    actual_flags = (
        binding.separate_approval_required,
        binding.external_authorization_required,
        binding.publication_authorization_required,
        binding.external_transmission_authorization_required,
    )
    if binding.unresolved_review_requirement_ids != unresolved or actual_flags != flags:
        raise DecisionPipelinePackageBindingError("decision package review binding mismatch")
    lineage_ids = tuple(
        sorted(
            (item.decision_package_lineage_reference_id for item in package.lineage_references),
            key=str,
        )
    )
    provenance_ids = tuple(
        sorted(
            (
                item.decision_package_provenance_reference_id
                for item in package.provenance_references
            ),
            key=str,
        )
    )
    if binding.lineage_reference_ids != lineage_ids:
        raise OrphanDecisionPipelineReferenceError("decision package lineage mismatch")
    if binding.provenance_reference_ids != provenance_ids:
        raise OrphanDecisionPipelineReferenceError("decision package provenance mismatch")
    if (
        binding.policy_revision != package.policy_revision
        or binding.authorization_revision != package.authorization_revision
        or binding.registry_revision != package.registry_revision
    ):
        raise DecisionPipelineVersionError("decision package revision mismatch")
    if binding.bound_at < package.recorded_at:
        raise DecisionPipelinePackageBindingError("package binding precedes package")
    return binding


def validate_decision_pipeline_stage_record(
    record: DecisionPipelineStageRecord,
    pipeline_id,
    binding_ids,
    review_ids,
    root_lineage_id,
    root_lineage_digest_reference,
) -> DecisionPipelineStageRecord:
    if record.decision_pipeline_id != pipeline_id:
        raise DecisionPipelineStageError("stage pipeline identity mismatch")
    if record.package_binding_ids != binding_ids:
        raise OrphanDecisionPipelineReferenceError("stage package binding mismatch")
    if record.review_requirement_ids != review_ids:
        raise OrphanDecisionPipelineReferenceError("stage review binding mismatch")
    if (
        record.lineage_id != root_lineage_id
        or record.lineage_digest_reference != root_lineage_digest_reference
    ):
        raise DecisionPipelineStageError("stage lineage mismatch")
    return record


def validate_decision_release_gate_record(
    record: DecisionReleaseGateRecord,
    pipeline: DecisionPipeline,
    package_ids,
    unresolved_review_ids,
) -> DecisionReleaseGateRecord:
    if record.decision_pipeline_id != pipeline.decision_pipeline_id:
        raise DecisionReleaseGateError("release gate pipeline mismatch")
    if record.decision_package_ids != package_ids:
        raise OrphanDecisionPipelineReferenceError("release gate package mismatch")
    if record.unresolved_review_requirement_ids != unresolved_review_ids:
        raise DecisionReleaseGateError("release gate review mismatch")
    _scope(record, pipeline.tenant_id, pipeline.organization_id)
    _classification(record.classification, pipeline.classification)
    if (
        record.root_lineage_id != pipeline.root_lineage_id
        or record.root_lineage_digest_reference != pipeline.root_lineage_digest_reference
    ):
        raise DecisionReleaseGateError("release gate lineage mismatch")
    if (
        record.policy_revision != pipeline.policy_revision
        or record.authorization_revision != pipeline.authorization_revision
        or record.registry_revision != pipeline.registry_revision
    ):
        raise DecisionPipelineVersionError("release gate revision mismatch")
    return record


def validate_decision_pipeline_lineage_reference(
    reference: DecisionPipelineLineageReference,
    pipeline: DecisionPipeline,
    package_ids,
    binding_ids,
    stage_ids,
    gate_ids,
) -> DecisionPipelineLineageReference:
    if reference.decision_pipeline_id != pipeline.decision_pipeline_id:
        raise DecisionPipelineLineageError("pipeline lineage identity mismatch")
    if pipeline.decision_pipeline_id in reference.parent_decision_pipeline_ids:
        raise DecisionPipelineLineageError("decision pipeline is its own parent")
    if (
        reference.root_lineage_id != pipeline.root_lineage_id
        or reference.root_lineage_digest_reference != pipeline.root_lineage_digest_reference
    ):
        raise DecisionPipelineLineageError("pipeline lineage root mismatch")
    if (
        reference.decision_package_ids,
        reference.package_binding_ids,
        reference.stage_record_ids,
        reference.release_gate_record_ids,
    ) != (package_ids, binding_ids, stage_ids, gate_ids):
        raise OrphanDecisionPipelineReferenceError("pipeline lineage reference mismatch")
    return reference


def validate_decision_pipeline_provenance_reference(
    reference: DecisionPipelineProvenanceReference,
    pipeline: DecisionPipeline,
    package_ids,
) -> DecisionPipelineProvenanceReference:
    if reference.decision_pipeline_id != pipeline.decision_pipeline_id:
        raise DecisionPipelineProvenanceError("pipeline provenance identity mismatch")
    if reference.decision_package_ids != package_ids:
        raise OrphanDecisionPipelineReferenceError("pipeline provenance package mismatch")
    if (
        reference.policy_revision != pipeline.policy_revision
        or reference.authorization_revision != pipeline.authorization_revision
        or reference.registry_revision != pipeline.registry_revision
    ):
        raise DecisionPipelineVersionError("pipeline provenance revision mismatch")
    return reference


def validate_decision_pipeline_audit_metadata(
    metadata: DecisionPipelineAuditMetadata,
) -> DecisionPipelineAuditMetadata:
    if metadata.unresolved_review_count < 0:
        raise DecisionPipelineAuditMetadataError("invalid unresolved review count")
    return metadata


def _ordered_unique(keys, field) -> None:
    if keys != tuple(sorted(keys)):
        raise DecisionPipelineOrderingError(f"{field} are not canonical")
    if len(keys) != len(set(keys)):
        raise DuplicateDecisionPipelineReferenceError(f"duplicate {field}")


def validate_decision_pipeline(
    pipeline: DecisionPipeline,
    decision_packages: tuple[DecisionPackage, ...],
) -> DecisionPipeline:
    package_map = {item.decision_package_id: item for item in decision_packages}
    if len(package_map) != len(decision_packages):
        raise DuplicateDecisionPipelineReferenceError("duplicate decision package")
    binding_keys = tuple(
        (
            str(item.decision_package_id),
            str(item.decision_pipeline_package_binding_id),
        )
        for item in pipeline.package_bindings
    )
    stage_keys = tuple(
        (item.stage_sequence, str(item.decision_pipeline_stage_record_id))
        for item in pipeline.stage_records
    )
    gate_keys = tuple(
        (item.recorded_at, str(item.decision_release_gate_record_id))
        for item in pipeline.release_gate_records
    )
    lineage_keys = tuple(
        str(item.decision_pipeline_lineage_reference_id)
        for item in pipeline.lineage_references
    )
    provenance_keys = tuple(
        str(item.decision_pipeline_provenance_reference_id)
        for item in pipeline.provenance_references
    )
    for keys, field in (
        (binding_keys, "package bindings"),
        (stage_keys, "stage records"),
        (gate_keys, "release gate records"),
        (lineage_keys, "lineage references"),
        (provenance_keys, "provenance references"),
    ):
        _ordered_unique(keys, field)
    if set(item.decision_package_id for item in pipeline.package_bindings) != set(package_map):
        raise OrphanDecisionPipelineReferenceError("pipeline package source mismatch")
    binding_ids = tuple(
        sorted(
            (item.decision_pipeline_package_binding_id for item in pipeline.package_bindings),
            key=str,
        )
    )
    package_ids = tuple(sorted(package_map, key=str))
    review_ids = tuple(
        sorted(
            {
                item
                for binding in pipeline.package_bindings
                for item in binding.unresolved_review_requirement_ids
            },
            key=str,
        )
    )
    for binding in pipeline.package_bindings:
        package = package_map[binding.decision_package_id]
        validate_decision_pipeline_package_binding(binding, package)
        _scope(binding, pipeline.tenant_id, pipeline.organization_id)
        _classification(pipeline.classification, binding.classification)
        if binding.bound_at > pipeline.recorded_at:
            raise DecisionPipelineError("binding follows pipeline")
    expected_sequence = 1
    for record in pipeline.stage_records:
        if record.stage_sequence != expected_sequence:
            raise DecisionPipelineStageError("stage sequence must be contiguous from one")
        expected_sequence += 1
        validate_decision_pipeline_stage_record(
            record,
            pipeline.decision_pipeline_id,
            binding_ids,
            review_ids,
            pipeline.root_lineage_id,
            pipeline.root_lineage_digest_reference,
        )
        _classification(pipeline.classification, record.classification)
        if record.recorded_at > pipeline.recorded_at:
            raise DecisionPipelineStageError("stage follows pipeline")
    if pipeline.stage_records and pipeline.current_stage is not pipeline.stage_records[-1].stage:
        raise DecisionPipelineStageError("current stage mismatch")
    flags = tuple(
        (
            binding.separate_approval_required,
            binding.external_authorization_required,
            binding.publication_authorization_required,
            binding.external_transmission_authorization_required,
        )
        for binding in pipeline.package_bindings
    )
    for gate in pipeline.release_gate_records:
        validate_decision_release_gate_record(gate, pipeline, package_ids, review_ids)
        gate_flags = (
            gate.separate_approval_required,
            gate.external_authorization_required,
            gate.publication_authorization_required,
            gate.external_transmission_authorization_required,
        )
        if any(gate_flags != item for item in flags):
            raise DecisionReleaseGateError("release gate declaration mismatch")
        if gate.recorded_at > pipeline.recorded_at:
            raise DecisionReleaseGateError("release gate follows pipeline")
    stage_ids = tuple(
        sorted((item.decision_pipeline_stage_record_id for item in pipeline.stage_records), key=str)
    )
    gate_ids = tuple(
        sorted(
            (item.decision_release_gate_record_id for item in pipeline.release_gate_records),
            key=str,
        )
    )
    for reference in pipeline.lineage_references:
        validate_decision_pipeline_lineage_reference(
            reference, pipeline, package_ids, binding_ids, stage_ids, gate_ids
        )
        if reference.created_at > pipeline.recorded_at:
            raise DecisionPipelineLineageError("lineage follows pipeline")
    for reference in pipeline.provenance_references:
        validate_decision_pipeline_provenance_reference(reference, pipeline, package_ids)
        if reference.recorded_at > pipeline.recorded_at:
            raise DecisionPipelineProvenanceError("provenance follows pipeline")
    if pipeline.audit_metadata is not None:
        audit = validate_decision_pipeline_audit_metadata(pipeline.audit_metadata)
        _scope(audit, pipeline.tenant_id, pipeline.organization_id)
        _classification(audit.classification, pipeline.classification)
        gate = pipeline.release_gate_records[0] if pipeline.release_gate_records else None
        expected = (
            pipeline.decision_pipeline_id,
            pipeline.pipeline_version,
            len(pipeline.package_bindings),
            len(pipeline.stage_records),
            len(pipeline.release_gate_records),
            len(review_ids),
            len(gate.blocking_security_reference_ids) if gate is not None else 0,
            len(gate.blocking_legal_reference_ids) if gate is not None else 0,
            len(gate.blocking_policy_reference_ids) if gate is not None else 0,
            len(gate.release_condition_reference_ids) if gate is not None else 0,
            len(pipeline.lineage_references),
            len(pipeline.provenance_references),
            pipeline.policy_revision,
            pipeline.registry_revision,
            pipeline.recorded_at,
        )
        actual = (
            audit.decision_pipeline_id,
            audit.pipeline_version,
            audit.package_binding_count,
            audit.stage_record_count,
            audit.release_gate_record_count,
            audit.unresolved_review_count,
            audit.blocking_security_reference_count,
            audit.blocking_legal_reference_count,
            audit.blocking_policy_reference_count,
            audit.release_condition_reference_count,
            audit.lineage_reference_count,
            audit.provenance_reference_count,
            audit.policy_revision,
            audit.registry_revision,
            audit.created_at,
        )
        if actual != expected:
            raise DecisionPipelineAuditMetadataError("pipeline audit metadata mismatch")
    return pipeline


def build_decision_pipeline(request: DecisionPipelineRequest) -> DecisionPipeline:
    validate_decision_pipeline(request.pipeline, request.decision_packages)
    return request.pipeline.model_copy()
