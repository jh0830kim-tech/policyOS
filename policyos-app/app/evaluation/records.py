"""Evaluation item, artifact, reproducibility, registry, and bindings."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.cross_validation.domain import CrossValidationPlan
from app.evaluation._base import EvaluationModel
from app.evaluation.datasets import EvaluationDatasetReference
from app.evaluation.domain import EvaluationDefinition
from app.evaluation.errors import (
    CrossValidationEvaluationBindingError,
    EvaluationAuthorizationBindingError,
    EvaluationItemRecordError,
    EvaluationRegistryError,
)
from app.evaluation.policies import EvaluationPolicyReference, EvaluatorReference
from app.execution.validation import require_aware
from app.zero_trust.evaluation_data import (
    EvaluationDataAccessContext,
    EvaluationDataAccessDecision,
    EvaluationDataAccessOutcome,
    EvaluationDataType,
)
from app.zero_trust.execution_tiers import ExecutionTier

if TYPE_CHECKING:
    from app.evaluation.datasets import (
        EvaluationExpectedOutputReference,
        EvaluationHiddenLabelReference,
        EvaluationInputReference,
        EvaluationReferenceMaterialReference,
    )
    from app.zero_trust.lineage import DelegationLineageRecord


def _canonical(value, name: str):
    if tuple(sorted(set(value), key=str)) != value:
        raise ValueError(f"{name} must be canonical and unique")
    return value


class EvaluationItemState(StrEnum):
    PENDING = "pending"
    READY = "ready"
    EVALUATED = "evaluated"
    SKIPPED = "skipped"
    FAILED = "failed"
    QUARANTINED = "quarantined"
    INVALIDATED = "invalidated"


class EvaluationItemRecord(EvaluationModel):
    evaluation_item_record_id: UUID
    evaluation_run_id: UUID
    item_id: str = Field(min_length=1, max_length=200)
    input_reference_id: UUID
    target_output_reference: str = Field(min_length=1, max_length=300)
    reference_material_reference_ids: tuple[UUID, ...] = ()
    hidden_label_reference_id: UUID | None = None
    expected_output_reference_id: UUID | None = None
    evaluator_observation_reference: str | None = Field(default=None, max_length=300)
    item_state: EvaluationItemState
    created_at: datetime

    @field_validator("reference_material_reference_ids")
    @classmethod
    def references(cls, value):
        return _canonical(value, "reference material")

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


def validate_unique_evaluation_items(items: tuple[EvaluationItemRecord, ...]) -> None:
    identities = tuple((item.evaluation_run_id, item.item_id) for item in items)
    if len(identities) != len(set(identities)):
        raise EvaluationItemRecordError("duplicate evaluation item identity")


def validate_evaluation_item_record(
    item: EvaluationItemRecord,
    *,
    input_reference: EvaluationInputReference,
    reference_materials: tuple[EvaluationReferenceMaterialReference, ...] = (),
    hidden_label: EvaluationHiddenLabelReference | None = None,
    expected_output: EvaluationExpectedOutputReference | None = None,
    expected_run_id: UUID,
    expected_dataset_split_reference_id: UUID,
) -> None:
    references = (input_reference, *reference_materials)
    if hidden_label is not None:
        references += (hidden_label,)
    if expected_output is not None:
        references += (expected_output,)
    if item.evaluation_run_id != expected_run_id:
        raise EvaluationItemRecordError("evaluation item run mismatch")
    if any(
        reference.item_id != item.item_id
        or reference.dataset_split_reference_id != expected_dataset_split_reference_id
        for reference in references
    ):
        raise EvaluationItemRecordError("evaluation item reference mismatch")
    if input_reference.evaluation_input_reference_id != item.input_reference_id:
        raise EvaluationItemRecordError("evaluation input identity mismatch")
    if tuple(reference.reference_material_reference_id for reference in reference_materials) != (
        item.reference_material_reference_ids
    ):
        raise EvaluationItemRecordError("evaluation reference-material binding mismatch")
    if (hidden_label.hidden_label_reference_id if hidden_label else None) != (
        item.hidden_label_reference_id
    ) or (expected_output.expected_output_reference_id if expected_output else None) != (
        item.expected_output_reference_id
    ):
        raise EvaluationItemRecordError("protected evaluation reference binding mismatch")
    if hidden_label is not None and hidden_label.visible_to_evaluated_model:
        raise EvaluationItemRecordError("hidden label exposed to evaluated model")
    if expected_output is not None and expected_output.visible_to_evaluated_model:
        raise EvaluationItemRecordError("expected output exposed to evaluated model")


class EvaluationArtifactType(StrEnum):
    TARGET_OUTPUT = "target_output"
    EVALUATOR_OBSERVATION = "evaluator_observation"
    INTERMEDIATE_REFERENCE = "intermediate_reference"
    FAILURE_DIAGNOSTIC_REFERENCE = "failure_diagnostic_reference"
    HUMAN_REVIEW_REFERENCE = "human_review_reference"
    EVALUATION_SUMMARY_REFERENCE = "evaluation_summary_reference"


class EvaluationArtifactReference(EvaluationModel):
    evaluation_artifact_reference_id: UUID
    evaluation_run_id: UUID
    artifact_type: EvaluationArtifactType
    artifact_storage_reference: str = Field(min_length=1, max_length=300)
    artifact_schema_reference: str = Field(min_length=1, max_length=300)
    artifact_digest_reference: str | None = Field(default=None, max_length=300)
    classification: DataClassification
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


class EvaluationReproducibilityRecord(EvaluationModel):
    reproducibility_record_id: UUID
    evaluation_run_id: UUID
    target_reference_id: UUID
    evaluation_registry_snapshot_reference_id: UUID | None = None
    model_id: str | None = Field(default=None, max_length=200)
    model_version: str | None = Field(default=None, max_length=100)
    provider_instance_id: str | None = Field(default=None, max_length=200)
    provider_adapter_version: str | None = Field(default=None, max_length=100)
    mcp_server_id: str | None = Field(default=None, max_length=200)
    mcp_protocol_version: str | None = Field(default=None, max_length=100)
    tool_id: str | None = Field(default=None, max_length=200)
    tool_schema_revision: str | None = Field(default=None, max_length=100)
    connector_id: str | None = Field(default=None, max_length=200)
    connector_operation: str | None = Field(default=None, max_length=100)
    dataset_reference_id: UUID
    dataset_manifest_reference_id: UUID | None = None
    dataset_version: str = Field(min_length=1, max_length=100)
    dataset_split_reference_id: UUID
    split_version: str = Field(min_length=1, max_length=100)
    evaluation_policy_reference_id: UUID
    policy_version: str = Field(min_length=1, max_length=100)
    evaluator_reference_id: UUID
    evaluator_version: str = Field(min_length=1, max_length=100)
    authorization_engine_version: str = Field(min_length=1, max_length=100)
    authorization_rule_set_version: str = Field(min_length=1, max_length=100)
    delegation_lineage_id: UUID
    delegation_lineage_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_environment_reference: str = Field(min_length=1, max_length=300)
    dependency_manifest_reference: str = Field(min_length=1, max_length=300)
    random_seed_reference: str | None = Field(default=None, max_length=300)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


def validate_evaluation_reproducibility_references(
    record: EvaluationReproducibilityRecord,
    *,
    registry_snapshot_reference_id: UUID | None,
    dataset_manifest_reference_id: UUID | None,
) -> None:
    if (
        record.evaluation_registry_snapshot_reference_id
        != registry_snapshot_reference_id
        or record.dataset_manifest_reference_id != dataset_manifest_reference_id
    ):
        raise EvaluationRegistryError("evaluation reproducibility reference mismatch")


class EvaluationDataAuthorizationBinding(EvaluationModel):
    evaluation_data_authorization_binding_id: UUID
    evaluation_run_id: UUID
    evaluation_data_access_context_id: UUID
    evaluation_data_access_decision_id: UUID
    actor_id: UUID
    agent_instance_id: UUID | None = None
    data_type: EvaluationDataType
    reference_id: UUID
    tenant_id: UUID
    organization_id: UUID
    execution_tier: ExecutionTier
    delegation_lineage_id: UUID
    delegation_lineage_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluated_agent_instance_id: UUID
    policy_revision: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def access_boundary(self):
        if self.execution_tier is not ExecutionTier.OFFLINE_EVALUATION:
            raise EvaluationAuthorizationBindingError("evaluation access requires offline tier")
        protected = self.data_type in {
            EvaluationDataType.HIDDEN_LABEL,
            EvaluationDataType.EXPECTED_OUTPUT,
        }
        if protected and self.agent_instance_id == self.evaluated_agent_instance_id:
            raise EvaluationAuthorizationBindingError(
                "evaluated agent cannot bind protected evaluation data"
            )
        return self


def validate_evaluation_artifact_access(
    binding: EvaluationDataAuthorizationBinding,
    context: EvaluationDataAccessContext,
    decision: EvaluationDataAccessDecision,
    *,
    evaluator_actor_id: UUID,
    evaluator_agent_instance_id: UUID | None,
    expected_evaluation_run_id: UUID,
    lineage: DelegationLineageRecord,
    expected_policy_revision: str,
) -> None:
    from app.zero_trust.lineage import verify_delegation_lineage_digest

    verify_delegation_lineage_digest(lineage.facts, lineage.digest)
    if (
        decision.outcome is not EvaluationDataAccessOutcome.ALLOW
        or decision.evaluation_access_decision_id != binding.evaluation_data_access_decision_id
        or decision.evaluation_access_request_id != context.evaluation_access_request_id
    ):
        raise EvaluationAuthorizationBindingError("evaluation data access was denied")
    actual = (
        binding.evaluation_data_access_context_id,
        binding.evaluation_run_id,
        binding.actor_id,
        binding.agent_instance_id,
        binding.tenant_id,
        binding.organization_id,
        binding.data_type,
        str(binding.reference_id),
        binding.execution_tier,
        binding.delegation_lineage_id,
        binding.delegation_lineage_digest,
        binding.policy_revision,
    )
    expected = (
        context.evaluation_access_request_id,
        expected_evaluation_run_id,
        evaluator_actor_id,
        evaluator_agent_instance_id,
        context.tenant_id,
        context.organization_id,
        context.data_type,
        context.evaluation_resource_id,
        context.execution_tier,
        lineage.lineage_id,
        lineage.digest.digest_value,
        expected_policy_revision,
    )
    if actual != expected:
        raise EvaluationAuthorizationBindingError("evaluation data authorization mismatch")
    if context.agent_instance_id != evaluator_agent_instance_id:
        raise EvaluationAuthorizationBindingError("evaluator agent context mismatch")
    if context.service_actor_id != evaluator_actor_id:
        raise EvaluationAuthorizationBindingError("evaluator actor context mismatch")
    if (
        context.tenant_id != lineage.facts.tenant_id
        or context.organization_id != lineage.facts.organization_id
        or context.on_behalf_of_user_id != lineage.facts.on_behalf_of_user_id
        or context.task_id != lineage.facts.task_id
    ):
        raise EvaluationAuthorizationBindingError("evaluation access lineage context mismatch")
    if binding.data_type in {EvaluationDataType.HIDDEN_LABEL, EvaluationDataType.EXPECTED_OUTPUT}:
        if (
            context.evaluated_model
            or binding.agent_instance_id == binding.evaluated_agent_instance_id
        ):
            raise EvaluationAuthorizationBindingError(
                "evaluated agent cannot access protected data"
            )


class CrossValidationEvaluationBinding(EvaluationModel):
    binding_id: UUID
    evaluation_run_id: UUID
    cross_validation_plan_id: UUID
    cross_validation_run_ids: tuple[UUID, ...]
    tenant_id: UUID
    organization_id: UUID
    consensus_decision_id: UUID | None = None
    secretary_handoff_id: UUID | None = None
    root_delegation_lineage_id: UUID
    root_delegation_lineage_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime

    @field_validator("cross_validation_run_ids")
    @classmethod
    def runs(cls, value):
        if not value:
            raise CrossValidationEvaluationBindingError("cross-validation runs are required")
        return _canonical(value, "cross-validation runs")

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


def validate_cross_validation_evaluation_binding(
    binding: CrossValidationEvaluationBinding,
    *,
    plan: CrossValidationPlan,
    root_lineage: DelegationLineageRecord,
    expected_organization_id: UUID,
) -> None:
    expected_run_ids = tuple(sorted((run.run_id for run in plan.run_specs), key=str))
    if (
        binding.cross_validation_plan_id != plan.plan_id
        or binding.cross_validation_run_ids != expected_run_ids
        or binding.tenant_id != plan.tenant_id
        or binding.organization_id != expected_organization_id
        or binding.root_delegation_lineage_id != root_lineage.lineage_id
        or binding.root_delegation_lineage_digest != root_lineage.digest.digest_value
        or root_lineage.facts.tenant_id != plan.tenant_id
        or root_lineage.facts.organization_id != expected_organization_id
    ):
        raise CrossValidationEvaluationBindingError("cross-validation evaluation lineage mismatch")


class EvaluationRegistrySnapshot(EvaluationModel):
    evaluation_registry_snapshot_id: UUID
    tenant_id: UUID
    organization_id: UUID
    registry_revision: int = Field(ge=1)
    definitions: tuple[EvaluationDefinition, ...] = ()
    datasets: tuple[EvaluationDatasetReference, ...] = ()
    policies: tuple[EvaluationPolicyReference, ...] = ()
    evaluators: tuple[EvaluatorReference, ...] = ()
    created_at: datetime

    @field_validator("definitions", "datasets", "policies", "evaluators")
    @classmethod
    def canonical_entries(cls, value, info):
        id_field = {
            "definitions": "evaluation_definition_id",
            "datasets": "dataset_reference_id",
            "policies": "evaluation_policy_reference_id",
            "evaluators": "evaluator_reference_id",
        }[info.field_name]
        ids = tuple(getattr(item, id_field) for item in value)
        if ids != tuple(sorted(set(ids), key=str)):
            raise EvaluationRegistryError("registry entries must be canonical and unique")
        return value

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def tenant_scope(self):
        for collection in (
            self.definitions,
            self.datasets,
            self.policies,
            self.evaluators,
        ):
            if any(
                item.tenant_id != self.tenant_id or item.organization_id != self.organization_id
                for item in collection
            ):
                raise EvaluationRegistryError("cross-tenant evaluation registry entry")
        return self


class EvaluationRegistrySnapshotReference(EvaluationModel):
    evaluation_registry_snapshot_reference_id: UUID
    registry_snapshot_id: UUID
    registry_revision: int = Field(ge=1)
    registry_schema_version: str = Field(min_length=1, max_length=100)
    registry_digest_reference: str = Field(min_length=1, max_length=300)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


def validate_evaluation_registry_snapshot_reference(
    reference: EvaluationRegistrySnapshotReference,
    snapshot: EvaluationRegistrySnapshot | None,
    *,
    expected_schema_version: str,
) -> None:
    if snapshot is None:
        raise EvaluationRegistryError("evaluation registry snapshot does not exist")
    if reference.registry_snapshot_id != snapshot.evaluation_registry_snapshot_id:
        raise EvaluationRegistryError("evaluation registry snapshot identity mismatch")
    if reference.registry_revision != snapshot.registry_revision:
        raise EvaluationRegistryError("evaluation registry snapshot revision mismatch")
    if reference.registry_schema_version != expected_schema_version:
        raise EvaluationRegistryError("evaluation registry snapshot schema mismatch")
