"""Tenant-scoped evaluation-data access protection contracts."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator

from app.ai.privacy import DataClassification
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware
from app.zero_trust.errors import EvaluationDataAccessError
from app.zero_trust.execution_tiers import ExecutionTier
from app.zero_trust.quarantine import QuarantineTriggerType


class EvaluationDataType(StrEnum):
    EVALUATION_INPUT = "evaluation_input"
    EVALUATION_REFERENCE = "evaluation_reference"
    HIDDEN_LABEL = "hidden_label"
    EXPECTED_OUTPUT = "expected_output"
    BENCHMARK_METADATA = "benchmark_metadata"
    EVALUATION_RESULT = "evaluation_result"


class EvaluationDataAccessOutcome(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class EvaluationDataAccessReason(StrEnum):
    ALLOWED_BY_POLICY = "allowed_by_policy"
    OFFLINE_TIER_REQUIRED = "offline_tier_required"
    EXPLICIT_AUTHORIZATION_REQUIRED = "explicit_authorization_required"
    EVALUATED_MODEL_EXPECTED_OUTPUT_DENIED = "evaluated_model_expected_output_denied"
    PRODUCTION_AGENT_HIDDEN_LABEL_DENIED = "production_agent_hidden_label_denied"
    TENANT_MISMATCH = "tenant_mismatch"
    CLASSIFICATION_DENIED = "classification_denied"


class EvaluationDataAccessContext(ExecutionModel):
    evaluation_access_request_id: UUID
    tenant_id: UUID
    organization_id: UUID
    on_behalf_of_user_id: UUID
    service_actor_id: UUID
    agent_instance_id: UUID
    task_id: UUID
    evaluation_resource_id: str = Field(min_length=1, max_length=200)
    data_type: EvaluationDataType
    classification: DataClassification
    execution_tier: ExecutionTier
    production_agent: bool
    evaluated_model: bool
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "requested_at")


class EvaluationDataPolicyFacts(ExecutionModel):
    authorized_tenant_id: UUID
    allowed_classifications: tuple[DataClassification, ...]
    explicit_data_type_authorizations: tuple[EvaluationDataType, ...]

    @field_validator("allowed_classifications", "explicit_data_type_authorizations")
    @classmethod
    def canonical(cls, value):
        if tuple(sorted(set(value), key=lambda item: item.value)) != value:
            raise EvaluationDataAccessError("evaluation policy facts must be canonical")
        return value


class EvaluationDataAccessDecision(ExecutionModel):
    evaluation_access_decision_id: UUID
    evaluation_access_request_id: UUID
    outcome: EvaluationDataAccessOutcome
    reason_codes: tuple[EvaluationDataAccessReason, ...]
    quarantine_trigger: QuarantineTriggerType | None
    decided_at: datetime

    @field_validator("reason_codes")
    @classmethod
    def canonical(cls, value):
        if not value or tuple(sorted(set(value), key=lambda item: item.value)) != value:
            raise EvaluationDataAccessError("evaluation decision reasons must be canonical")
        return value

    @field_validator("decided_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "decided_at")


def evaluate_evaluation_data_access(
    context: EvaluationDataAccessContext,
    facts: EvaluationDataPolicyFacts,
    *,
    evaluation_access_decision_id: UUID,
    decided_at: datetime,
) -> EvaluationDataAccessDecision:
    reasons: list[EvaluationDataAccessReason] = []
    protected = context.data_type in {
        EvaluationDataType.HIDDEN_LABEL,
        EvaluationDataType.EXPECTED_OUTPUT,
    }
    if context.execution_tier is not ExecutionTier.OFFLINE_EVALUATION:
        reasons.append(EvaluationDataAccessReason.OFFLINE_TIER_REQUIRED)
    if context.tenant_id != facts.authorized_tenant_id:
        reasons.append(EvaluationDataAccessReason.TENANT_MISMATCH)
    if context.classification not in facts.allowed_classifications:
        reasons.append(EvaluationDataAccessReason.CLASSIFICATION_DENIED)
    if context.data_type not in facts.explicit_data_type_authorizations:
        reasons.append(EvaluationDataAccessReason.EXPLICIT_AUTHORIZATION_REQUIRED)
    if context.production_agent and context.data_type is EvaluationDataType.HIDDEN_LABEL:
        reasons.append(EvaluationDataAccessReason.PRODUCTION_AGENT_HIDDEN_LABEL_DENIED)
    if context.evaluated_model and context.data_type is EvaluationDataType.EXPECTED_OUTPUT:
        reasons.append(EvaluationDataAccessReason.EVALUATED_MODEL_EXPECTED_OUTPUT_DENIED)
    reasons = sorted(set(reasons), key=lambda item: item.value)
    denied = bool(reasons)
    return EvaluationDataAccessDecision(
        evaluation_access_decision_id=evaluation_access_decision_id,
        evaluation_access_request_id=context.evaluation_access_request_id,
        outcome=EvaluationDataAccessOutcome.DENY if denied else EvaluationDataAccessOutcome.ALLOW,
        reason_codes=tuple(reasons or [EvaluationDataAccessReason.ALLOWED_BY_POLICY]),
        quarantine_trigger=(
            QuarantineTriggerType.EVALUATION_DATA_ACCESS_ATTEMPT if denied and protected else None
        ),
        decided_at=decided_at,
    )


class AuthorizedEvaluationDataAccessPermit(ExecutionModel):
    evaluation_data_permit_id: UUID
    evaluation_access_request_id: UUID
    evaluation_access_decision_id: UUID
    tenant_id: UUID
    organization_id: UUID
    agent_instance_id: UUID
    task_id: UUID
    evaluation_resource_id: str
    data_type: EvaluationDataType
    classification: DataClassification
    issued_at: datetime
    expires_at: datetime | None = None
    production_resource_access_allowed: bool = False

    @field_validator("issued_at", "expires_at")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name)


def issue_evaluation_data_permit(
    context: EvaluationDataAccessContext,
    decision: EvaluationDataAccessDecision,
    *,
    evaluation_data_permit_id: UUID,
    issued_at: datetime,
    expires_at: datetime | None = None,
) -> AuthorizedEvaluationDataAccessPermit:
    if (
        decision.outcome is not EvaluationDataAccessOutcome.ALLOW
        or decision.evaluation_access_request_id != context.evaluation_access_request_id
    ):
        raise EvaluationDataAccessError("evaluation data access was not authorized")
    if expires_at is not None and expires_at <= issued_at:
        raise EvaluationDataAccessError("evaluation permit expiry must follow issuance")
    return AuthorizedEvaluationDataAccessPermit(
        evaluation_data_permit_id=evaluation_data_permit_id,
        evaluation_access_request_id=context.evaluation_access_request_id,
        evaluation_access_decision_id=decision.evaluation_access_decision_id,
        tenant_id=context.tenant_id,
        organization_id=context.organization_id,
        agent_instance_id=context.agent_instance_id,
        task_id=context.task_id,
        evaluation_resource_id=context.evaluation_resource_id,
        data_type=context.data_type,
        classification=context.classification,
        issued_at=issued_at,
        expires_at=expires_at,
        production_resource_access_allowed=False,
    )
