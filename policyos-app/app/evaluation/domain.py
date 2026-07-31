"""Evaluation definitions and immutable target references."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.evaluation._base import EvaluationModel
from app.evaluation.errors import EvaluationDefinitionError, EvaluationTargetError
from app.execution.validation import require_aware
from app.zero_trust.execution_tiers import ExecutionTier

if TYPE_CHECKING:
    from app.zero_trust.lineage import DelegationLineageRecord


class EvaluationType(StrEnum):
    FUNCTIONAL_CORRECTNESS = "functional_correctness"
    LEGAL_GROUNDING = "legal_grounding"
    POLICY_GROUNDING = "policy_grounding"
    EVIDENCE_COVERAGE = "evidence_coverage"
    CITATION_INTEGRITY = "citation_integrity"
    SAFETY_COMPLIANCE = "safety_compliance"
    AUTHORIZATION_COMPLIANCE = "authorization_compliance"
    TOOL_USE_COMPLIANCE = "tool_use_compliance"
    CROSS_VALIDATION_CONSISTENCY = "cross_validation_consistency"
    SECRET_ISOLATION_COMPLIANCE = "secret_isolation_compliance"
    TENANT_ISOLATION_COMPLIANCE = "tenant_isolation_compliance"
    AUDIT_COMPLETENESS = "audit_completeness"
    CUSTOM_REFERENCED = "custom_referenced"


class EvaluationTargetType(StrEnum):
    MODEL_INVOCATION = "model_invocation"
    PROVIDER_INVOCATION = "provider_invocation"
    MCP_TOOL_INVOCATION = "mcp_tool_invocation"
    CONNECTOR_OPERATION = "connector_operation"
    CROSS_VALIDATION_RUN = "cross_validation_run"
    SECRETARY_HANDOFF = "secretary_handoff"
    EXECUTION_TASK = "execution_task"
    STORED_RESULT_REFERENCE = "stored_result_reference"
    COMPOSITE_EXECUTION = "composite_execution"


class EvaluationDefinition(EvaluationModel):
    evaluation_definition_id: UUID
    tenant_id: UUID
    organization_id: UUID
    name: str = Field(min_length=1, max_length=200)
    description_reference: str | None = Field(default=None, max_length=200)
    evaluation_type: EvaluationType
    target_type: EvaluationTargetType
    dataset_reference_id: UUID
    dataset_split_reference_id: UUID
    evaluation_policy_reference_id: UUID
    evaluator_reference_id: UUID
    execution_tier: ExecutionTier
    classification: DataClassification
    risk_level: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,49}$")
    enabled: bool
    definition_revision: int = Field(ge=1)
    created_by_user_id: UUID
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def offline_only(self):
        if self.execution_tier is not ExecutionTier.OFFLINE_EVALUATION:
            raise EvaluationDefinitionError("evaluation definition requires offline tier")
        return self


class EvaluationTargetReference(EvaluationModel):
    target_reference_id: UUID
    target_type: EvaluationTargetType
    tenant_id: UUID
    organization_id: UUID
    on_behalf_of_user_id: UUID
    service_actor_id: UUID
    agent_instance_id: UUID
    task_id: UUID
    execution_id: UUID | None = None
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
    cross_validation_plan_id: UUID | None = None
    cross_validation_run_id: UUID | None = None
    secretary_handoff_id: UUID | None = None
    repository_result_reference_id: UUID | None = None
    delegation_lineage_id: UUID
    delegation_lineage_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    classification: DataClassification
    risk_level: str = Field(min_length=1, max_length=50)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def concrete(self):
        artifacts = (
            self.execution_id,
            self.model_id,
            self.provider_instance_id,
            self.mcp_server_id,
            self.tool_id,
            self.connector_id,
            self.cross_validation_run_id,
            self.secretary_handoff_id,
            self.repository_result_reference_id,
        )
        if not any(artifacts):
            raise EvaluationTargetError("evaluation target requires an execution artifact")
        version_pairs = (
            ("model", self.model_id, self.model_version),
            ("provider", self.provider_instance_id, self.provider_adapter_version),
            ("MCP server", self.mcp_server_id, self.mcp_protocol_version),
            ("tool", self.tool_id, self.tool_schema_revision),
        )
        for name, identity, version in version_pairs:
            if (identity is None) != (version is None):
                raise EvaluationTargetError(f"{name} identity and version must be paired")
        return self


def validate_evaluation_target_lineage(
    target: EvaluationTargetReference,
    lineage: DelegationLineageRecord,
) -> None:
    from app.zero_trust.lineage import verify_delegation_lineage_digest

    verify_delegation_lineage_digest(lineage.facts, lineage.digest)
    actual = (
        target.delegation_lineage_id,
        target.delegation_lineage_digest,
        target.tenant_id,
        target.organization_id,
        target.on_behalf_of_user_id,
        target.service_actor_id,
        target.agent_instance_id,
        target.task_id,
    )
    expected = (
        lineage.lineage_id,
        lineage.digest.digest_value,
        lineage.facts.tenant_id,
        lineage.facts.organization_id,
        lineage.facts.on_behalf_of_user_id,
        lineage.facts.service_actor_id,
        lineage.facts.agent_instance_id,
        lineage.facts.task_id,
    )
    if actual != expected:
        raise EvaluationTargetError("evaluation target delegation lineage mismatch")
