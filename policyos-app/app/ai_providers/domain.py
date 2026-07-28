"""Immutable provider-neutral invocation contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai_models import ModelCapability, ModelId, ProviderInstanceId, ProviderType
from app.ai_selection import AuthorizedInvocationPermit, SelectionAction
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware

AdapterId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]{1,99}$")]
SafeId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$")]


def _canonical(value, field_name, *, maximum):
    if len(value) > maximum or tuple(sorted(set(value), key=str)) != value:
        raise ValueError(f"{field_name} must be canonical, unique, and bounded")
    return value


class NormalizedMessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class NormalizedContentKind(StrEnum):
    TEXT = "text"


class NormalizedContentPart(ExecutionModel):
    kind: NormalizedContentKind = NormalizedContentKind.TEXT
    text: str = Field(min_length=1, max_length=32_000)

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, value):
        if not value.strip():
            raise ValueError("normalized text must not be blank")
        return value


class NormalizedMessage(ExecutionModel):
    role: NormalizedMessageRole
    content: tuple[NormalizedContentPart, ...] = Field(min_length=1, max_length=50)


class NormalizedGenerationParameters(ExecutionModel):
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int | None = Field(default=None, ge=1, le=1_000_000)
    top_p: float | None = Field(default=None, gt=0, le=1)
    stop_sequences: tuple[Annotated[str, Field(min_length=1, max_length=200)], ...] = ()
    deterministic_seed: int | None = Field(default=None, ge=0, le=2_147_483_647)

    @field_validator("stop_sequences")
    @classmethod
    def canonical_stops(cls, value):
        return _canonical(value, "stop sequences", maximum=8)


class NormalizedOutputFormat(StrEnum):
    TEXT = "text"
    STRUCTURED_JSON = "structured_json"


class NormalizedOutputConstraint(ExecutionModel):
    format: NormalizedOutputFormat = NormalizedOutputFormat.TEXT


class NormalizedInvocationKind(StrEnum):
    TEXT_GENERATION = "text_generation"


class ProviderAdapterIdentity(ExecutionModel):
    adapter_id: AdapterId
    provider_family: ProviderType
    provider_instance_id: ProviderInstanceId | None = None
    adapter_version: SafeId
    supported_invocation_kind: NormalizedInvocationKind
    supported_capabilities: tuple[ModelCapability, ...]

    @field_validator("supported_capabilities")
    @classmethod
    def canonical_capabilities(cls, value):
        return _canonical(value, "adapter capabilities", maximum=20)


class NormalizedModelInvocationRequest(ExecutionModel):
    invocation_id: UUID
    permit_id: UUID
    selection_request_id: UUID
    authorization_decision_id: UUID
    approval_id: UUID | None = None
    tenant_id: UUID
    resource_id: SafeId
    action: SelectionAction
    purpose: SafeId
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    provider_instance_id: ProviderInstanceId
    model_id: ModelId
    adapter_id: AdapterId
    invocation_kind: NormalizedInvocationKind = NormalizedInvocationKind.TEXT_GENERATION
    messages: tuple[NormalizedMessage, ...] = Field(min_length=1, max_length=100)
    requested_capabilities: tuple[ModelCapability, ...] = ()
    output_constraint: NormalizedOutputConstraint = Field(
        default_factory=NormalizedOutputConstraint
    )
    generation_parameters: NormalizedGenerationParameters = Field(
        default_factory=NormalizedGenerationParameters
    )
    created_at: datetime

    @field_validator("requested_capabilities")
    @classmethod
    def canonical_capabilities(cls, value):
        return _canonical(value, "requested capabilities", maximum=20)

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


class NormalizedResultStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class NormalizedFinishReason(StrEnum):
    STOP = "stop"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"
    TOOL_REQUEST = "tool_request"
    ERROR = "error"
    UNKNOWN = "unknown"


class NormalizedOutputPart(ExecutionModel):
    kind: NormalizedContentKind = NormalizedContentKind.TEXT
    text: str = Field(min_length=1, max_length=64_000)


class NormalizedInvocationOutput(ExecutionModel):
    parts: tuple[NormalizedOutputPart, ...] = Field(min_length=1, max_length=50)


class NormalizedTokenUsage(ExecutionModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def exact_total(self):
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError("total tokens must equal input plus output tokens")
        return self


class NormalizedInvocationFailure(ExecutionModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,99}$")
    message: str = Field(min_length=1, max_length=500)


class NormalizedModelInvocationResult(ExecutionModel):
    invocation_id: UUID
    permit_id: UUID
    selection_request_id: UUID
    authorization_decision_id: UUID
    approval_id: UUID | None = None
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    provider_instance_id: ProviderInstanceId
    model_id: ModelId
    adapter_id: AdapterId
    status: NormalizedResultStatus
    output: NormalizedInvocationOutput | None = None
    usage: NormalizedTokenUsage | None = None
    finish_reason: NormalizedFinishReason
    failure: NormalizedInvocationFailure | None = None
    started_at: datetime
    completed_at: datetime
    provider_request_id: SafeId | None = None

    @field_validator("started_at", "completed_at")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def consistent_result(self):
        if self.completed_at < self.started_at:
            raise ValueError("completion cannot precede invocation start")
        if self.status is NormalizedResultStatus.SUCCEEDED:
            if self.output is None or self.failure is not None:
                raise ValueError("successful invocation requires output and no failure")
            if self.finish_reason is NormalizedFinishReason.ERROR:
                raise ValueError("successful invocation cannot have error finish reason")
        else:
            if self.failure is None or self.output is not None:
                raise ValueError("failed invocation requires failure and no output")
            if self.finish_reason is not NormalizedFinishReason.ERROR:
                raise ValueError("failed invocation requires error finish reason")
        return self


class ProviderInvocationAuditRecord(ExecutionModel):
    audit_id: UUID
    invocation_id: UUID
    permit_id: UUID
    decision_id: UUID
    approval_id: UUID | None
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    provider_instance_id: ProviderInstanceId
    model_id: ModelId
    adapter_id: AdapterId
    status: NormalizedResultStatus
    finish_reason: NormalizedFinishReason
    usage: NormalizedTokenUsage | None
    started_at: datetime
    completed_at: datetime
    recorded_at: datetime

    @field_validator("started_at", "completed_at", "recorded_at")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name)


def create_provider_invocation_audit_record(
    result: NormalizedModelInvocationResult,
    *,
    audit_id: UUID,
    recorded_at: datetime,
) -> ProviderInvocationAuditRecord:
    return ProviderInvocationAuditRecord(
        audit_id=audit_id,
        invocation_id=result.invocation_id,
        permit_id=result.permit_id,
        decision_id=result.authorization_decision_id,
        approval_id=result.approval_id,
        registry_id=result.registry_id,
        registry_revision=result.registry_revision,
        provider_instance_id=result.provider_instance_id,
        model_id=result.model_id,
        adapter_id=result.adapter_id,
        status=result.status,
        finish_reason=result.finish_reason,
        usage=result.usage,
        started_at=result.started_at,
        completed_at=result.completed_at,
        recorded_at=recorded_at,
    )


def request_lineage(request: NormalizedModelInvocationRequest):
    return (
        request.permit_id,
        request.selection_request_id,
        request.authorization_decision_id,
        request.approval_id,
        request.tenant_id,
        request.resource_id,
        request.action,
        request.purpose,
        request.registry_id,
        request.registry_revision,
        request.provider_instance_id,
        request.model_id,
    )


def permit_lineage(permit: AuthorizedInvocationPermit):
    return (
        permit.permit_id,
        permit.selection_request_id,
        permit.authorization_decision_id,
        permit.approval_id,
        permit.tenant_id,
        permit.resource_id,
        permit.action,
        permit.purpose,
        permit.registry_id,
        permit.registry_revision,
        permit.provider_instance_id,
        permit.model_id,
    )
