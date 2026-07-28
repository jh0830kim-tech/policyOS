"""Immutable contracts for one exact model-selection intent."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.ai_models import ModelCapability, ModelId, ProviderInstanceId
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware

BoundedId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$")]


class SelectionAction(StrEnum):
    INTERNAL_SUMMARY = "internal_summary"
    INTERNAL_ANALYSIS = "internal_analysis"
    EXTERNAL_MODEL_PROCESSING = "external_model_processing"
    EXTERNAL_TRANSMISSION = "external_transmission"
    TOOL_INVOCATION = "tool_invocation"
    CONNECTOR_READ = "connector_read"
    CONNECTOR_WRITE = "connector_write"


class SelectionTargetType(StrEnum):
    MODEL = "model"
    TOOL = "tool"
    MCP_TOOL = "mcp_tool"
    CONNECTOR = "connector"


class TargetTrustBoundary(StrEnum):
    INTERNAL = "internal"
    PRIVATE_MANAGED = "private_managed"
    EXTERNAL = "external"


class SelectionRiskLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class ResourceType(StrEnum):
    DOCUMENT = "document"
    DATASET = "dataset"
    WORK_PRODUCT = "work_product"
    OTHER = "other"


class AuthorizationOutcome(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRES_HUMAN_APPROVAL = "requires_human_approval"


class AuthorizationReason(StrEnum):
    ALLOWED_BY_POLICY = "allowed_by_policy"
    EXTERNAL_PROVIDER_FORBIDDEN = "external_provider_forbidden"
    CLASSIFICATION_NOT_PERMITTED = "classification_not_permitted"
    TENANT_POLICY_DENY = "tenant_policy_deny"
    ACTION_NOT_PERMITTED = "action_not_permitted"
    PURPOSE_NOT_PERMITTED = "purpose_not_permitted"
    RESOURCE_NOT_PERMITTED = "resource_not_permitted"
    MODEL_NOT_SELECTABLE = "model_not_selectable"
    PROVIDER_NOT_SELECTABLE = "provider_not_selectable"
    REQUIRED_CAPABILITY_MISSING = "required_capability_missing"
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"
    POLICY_INPUT_INVALID = "policy_input_invalid"


def _canonical(value, name, *, maximum=50):
    if len(value) > maximum or tuple(sorted(set(value), key=str)) != value:
        raise ValueError(f"{name} must be canonical, unique, and bounded")
    return value


class ModelSelectionContext(ExecutionModel):
    selection_request_id: UUID
    tenant_id: UUID
    actor_id: BoundedId
    resource_id: BoundedId
    resource_type: ResourceType
    action: SelectionAction
    purpose: BoundedId
    classification: DataClassification
    risk_level: SelectionRiskLevel
    target_type: SelectionTargetType = SelectionTargetType.MODEL
    trust_boundary: TargetTrustBoundary
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    model_id: ModelId
    provider_instance_id: ProviderInstanceId
    requested_capabilities: tuple[ModelCapability, ...] = ()
    external_transmission: bool
    created_at: datetime

    @field_validator("actor_id", "resource_id", "purpose")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("selection identity must not be blank")
        return value

    @field_validator("requested_capabilities")
    @classmethod
    def canonical_capabilities(cls, value):
        return _canonical(value, "requested capabilities", maximum=20)

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def model_target_only(self):
        if self.target_type is not SelectionTargetType.MODEL:
            raise ValueError("CP2 supports model targets only")
        if self.external_transmission and self.action not in {
            SelectionAction.EXTERNAL_MODEL_PROCESSING,
            SelectionAction.EXTERNAL_TRANSMISSION,
        }:
            raise ValueError("external transmission requires an external action")
        return self


class SelectionPolicyFacts(ExecutionModel):
    policy_revision: BoundedId
    tenant_id: UUID
    permitted_actions: tuple[SelectionAction, ...]
    permitted_purposes: tuple[BoundedId, ...]
    permitted_resource_ids: tuple[BoundedId, ...]
    permitted_classifications: tuple[DataClassification, ...]
    permitted_model_ids: tuple[ModelId, ...]
    permitted_provider_instance_ids: tuple[ProviderInstanceId, ...]
    external_forbidden_classifications: tuple[DataClassification, ...] = ()
    human_approval_actions: tuple[SelectionAction, ...] = ()

    @field_validator(
        "permitted_actions",
        "permitted_purposes",
        "permitted_resource_ids",
        "permitted_classifications",
        "permitted_model_ids",
        "permitted_provider_instance_ids",
        "external_forbidden_classifications",
        "human_approval_actions",
    )
    @classmethod
    def canonical_values(cls, value, info):
        return _canonical(value, info.field_name)


class ModelSelectionAuthorizationDecision(ExecutionModel):
    decision_id: UUID
    selection_request_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    action: SelectionAction
    purpose: BoundedId
    classification: DataClassification
    target_type: SelectionTargetType
    trust_boundary: TargetTrustBoundary
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    model_id: ModelId
    provider_instance_id: ProviderInstanceId
    outcome: AuthorizationOutcome
    reasons: tuple[AuthorizationReason, ...]
    approval_required: bool
    policy_revision: BoundedId
    decided_at: datetime

    @field_validator("reasons")
    @classmethod
    def canonical_reasons(cls, value):
        if not value:
            raise ValueError("authorization reasons must not be empty")
        return _canonical(value, "authorization reasons", maximum=20)

    @field_validator("decided_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "decided_at")

    @model_validator(mode="after")
    def consistent_outcome(self):
        required = self.outcome is AuthorizationOutcome.REQUIRES_HUMAN_APPROVAL
        if self.approval_required != required:
            raise ValueError("approval requirement must match authorization outcome")
        return self
