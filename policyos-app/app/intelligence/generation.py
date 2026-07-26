"""Grounded, provider-neutral narrative generation service."""

from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import Field, ValidationError, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.execution.validation import require_aware, require_not_lower
from app.intelligence.generation_errors import (
    NarrativeDraftNormalizationError,
    NarrativeGenerationClassificationError,
    NarrativeGenerationContextError,
    NarrativeGenerationError,
    NarrativeGenerationIdentityError,
    NarrativeGenerationRequestError,
    NarrativeGenerationResultMismatchError,
    NarrativeProviderCapabilityError,
    NarrativeProviderInvocationError,
)
from app.intelligence.narrative import (
    NarrativeDraft,
    NarrativeModel,
    NarrativePolicy,
    NarrativeRequest,
    NarrativeSectionPlan,
    NarrativeSourceBundle,
    NarrativeValidationResult,
    validate_narrative_draft,
)
from app.intelligence.narrative_provider import (
    GROUNDED_CAPABILITY,
    NARRATIVE_SCHEMA_VERSION,
    NarrativeProviderAdapter,
    NarrativeProviderMetrics,
    NarrativeProviderRequest,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class NarrativeGenerationRequest(NarrativeModel):
    generation_id: UUID
    narrative_request: NarrativeRequest
    source_bundle: NarrativeSourceBundle
    section_plan: tuple[NarrativeSectionPlan, ...]
    policy: NarrativePolicy
    provider_capability: str = GROUNDED_CAPABILITY
    issued_at: datetime
    deadline: datetime
    expected_classification: DataClassification
    expected_output_schema_version: str = NARRATIVE_SCHEMA_VERSION

    @field_validator("issued_at", "deadline")
    @classmethod
    def aware_times(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def consistent(self):
        if self.deadline <= self.issued_at:
            raise NarrativeGenerationRequestError("Generation deadline must follow issue time")
        if self.policy != self.narrative_request.policy:
            raise NarrativeGenerationRequestError("Generation policy does not match request")
        if self.expected_output_schema_version != NARRATIVE_SCHEMA_VERSION:
            raise NarrativeGenerationRequestError("Unsupported narrative output schema version")
        if self.provider_capability != GROUNDED_CAPABILITY:
            raise NarrativeProviderCapabilityError("Unsupported narrative provider capability")
        self.source_bundle.validate_request(self.narrative_request)
        try:
            require_not_lower(self.expected_classification, self.source_bundle.classification)
            require_not_lower(self.narrative_request.classification, self.expected_classification)
            require_not_lower(self.expected_classification, self.narrative_request.classification)
        except ValueError as exc:
            raise NarrativeGenerationClassificationError(
                "Generation classification is inconsistent"
            ) from exc
        ids = [item.section_id for item in self.section_plan]
        orders = [item.order for item in self.section_plan]
        if not self.section_plan or len(ids) != len(set(ids)) or orders != list(range(len(orders))):
            raise NarrativeGenerationRequestError("Section plan is not canonical")
        allowed = set(self.source_bundle.allowed_step_ids)
        if any(not set(item.source_step_ids) <= allowed for item in self.section_plan):
            raise NarrativeGenerationRequestError("Section plan references an unknown source step")
        return self


class NarrativeGenerationContext(NarrativeModel):
    generation_id: UUID
    request_id: UUID
    execution_id: UUID
    organization_id: UUID
    actor_id: UUID
    correlation_id: str = Field(min_length=1, max_length=200)
    causation_id: str | None = Field(default=None, max_length=200)
    classification: DataClassification
    attempt: int = Field(default=1, ge=1, le=10)
    issued_at: datetime
    started_at: datetime
    deadline: datetime
    cancellation_requested: bool = False
    policy_version: str = Field(default="1.0", min_length=1, max_length=50)
    schema_version: str = NARRATIVE_SCHEMA_VERSION

    @field_validator("issued_at", "started_at", "deadline")
    @classmethod
    def aware_times(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def valid_times(self):
        if not self.issued_at <= self.started_at < self.deadline:
            raise NarrativeGenerationContextError("Generation context timestamps are invalid")
        if self.schema_version != NARRATIVE_SCHEMA_VERSION:
            raise NarrativeGenerationContextError("Unsupported generation context schema")
        return self


class NarrativeGenerationStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    INVALID_OUTPUT = "invalid_output"


class NarrativeGenerationSafeError(NarrativeModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,99}$")
    safe_message: str = Field(min_length=1, max_length=300)
    retryable: bool = False


class NarrativeGenerationOutcome(NarrativeModel):
    generation_id: UUID
    request_id: UUID
    execution_id: UUID
    provider_id: str = Field(pattern=r"^[a-z][a-z0-9_.]{1,99}$")
    status: NarrativeGenerationStatus
    draft: NarrativeDraft | None = None
    validation_result: NarrativeValidationResult | None = None
    retryable: bool = False
    metrics: NarrativeProviderMetrics = Field(
        default_factory=lambda: NarrativeProviderMetrics(provider_call_count=0)
    )
    warnings: tuple[str, ...] = ()
    started_at: datetime
    completed_at: datetime
    error: NarrativeGenerationSafeError | None = None

    @field_validator("started_at", "completed_at")
    @classmethod
    def aware_times(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def consistent(self):
        if self.completed_at < self.started_at:
            raise ValueError("Generation completion cannot precede start")
        if self.status is NarrativeGenerationStatus.SUCCEEDED:
            if (
                self.draft is None
                or self.validation_result is None
                or not self.validation_result.valid
            ):
                raise ValueError("Successful generation requires a valid draft")
            if self.error is not None:
                raise ValueError("Successful generation cannot contain an error")
        elif self.error is None:
            raise ValueError("Non-success generation requires a safe error")
        return self


class NarrativeGenerator(Protocol):
    async def generate(
        self, *, request: NarrativeGenerationRequest, context: NarrativeGenerationContext
    ) -> NarrativeGenerationOutcome: ...


def narrative_output_schema() -> dict:
    schema = NarrativeDraft.model_json_schema()
    properties = dict(schema["properties"])
    for name in ("request_id", "execution_id", "status", "generated_at"):
        properties.pop(name, None)
    required = [name for name in schema.get("required", ()) if name in properties]
    return {
        "$defs": schema.get("$defs", {}),
        "type": "object",
        "properties": {
            "generation_id": {"type": "string", "format": "uuid"},
            "schema_version": {"type": "string", "const": NARRATIVE_SCHEMA_VERSION},
            **properties,
        },
        "required": ["generation_id", "schema_version", *required],
        "additionalProperties": False,
    }


def build_grounded_narrative_provider_request(request, context) -> NarrativeProviderRequest:
    narrative = request.narrative_request
    return NarrativeProviderRequest(
        generation_id=request.generation_id,
        capability=request.provider_capability,
        language=narrative.language,
        locale=narrative.locale,
        purpose=narrative.purpose.value,
        format=narrative.format.value,
        audience=narrative.audience.value,
        tone=narrative.tone.value,
        sections=tuple(item.model_dump(mode="json") for item in request.section_plan),
        source_payload=request.source_bundle.narrative_input.model_dump(mode="json"),
        policy_payload=request.policy.model_dump(mode="json"),
        output_schema=narrative_output_schema(),
        maximum_output_characters=request.policy.maximum_output_characters,
        classification=context.classification,
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        request_id=context.request_id,
        deadline=context.deadline,
        idempotency_key=f"narrative.{request.generation_id}",
    )


class GroundedNarrativeGenerator:
    def __init__(self, adapter: NarrativeProviderAdapter, clock: Clock) -> None:
        if GROUNDED_CAPABILITY not in adapter.capabilities:
            raise NarrativeProviderCapabilityError("Adapter lacks grounded generation capability")
        self._adapter = adapter
        self._clock = clock

    async def generate(self, *, request, context) -> NarrativeGenerationOutcome:
        now = require_aware(self._clock.now(), "clock time")
        self._validate_identity(request, context)
        if context.cancellation_requested:
            return self._failure(
                request,
                context,
                now,
                NarrativeGenerationStatus.CANCELLED,
                NarrativeGenerationError("Narrative generation was cancelled"),
            )
        if now >= context.deadline:
            return self._failure(
                request,
                context,
                now,
                NarrativeGenerationStatus.TIMED_OUT,
                NarrativeGenerationError("Narrative generation deadline exceeded"),
                True,
            )
        provider_request = build_grounded_narrative_provider_request(request, context)
        try:
            result = await self._adapter.generate(provider_request)
        except NarrativeGenerationError as exc:
            completed = require_aware(self._clock.now(), "clock time")
            return self._failure(
                request, context, completed, NarrativeGenerationStatus.FAILED, exc, exc.retryable
            )
        except ValidationError:
            completed = require_aware(self._clock.now(), "clock time")
            error = NarrativeDraftNormalizationError("Narrative structured output is invalid")
            return self._failure(
                request,
                context,
                completed,
                NarrativeGenerationStatus.INVALID_OUTPUT,
                error,
                True,
            )
        except Exception:
            completed = require_aware(self._clock.now(), "clock time")
            error = NarrativeProviderInvocationError("Narrative provider invocation failed")
            return self._failure(
                request, context, completed, NarrativeGenerationStatus.FAILED, error
            )
        if (
            result.provider_id != self._adapter.provider_id
            or result.generation_id != request.generation_id
        ):
            raise NarrativeGenerationResultMismatchError(
                "Narrative provider result identity mismatch"
            )
        if result.completed_at >= context.deadline:
            error = NarrativeGenerationError("Narrative provider result arrived after deadline")
            return self._failure(
                request,
                context,
                result.completed_at,
                NarrativeGenerationStatus.TIMED_OUT,
                error,
                True,
                result.metrics,
            )
        try:
            payload = dict(result.structured_output)
            generation_id = payload.pop("generation_id")
            schema_version = payload.pop("schema_version")
            if (
                generation_id != str(request.generation_id)
                or schema_version != NARRATIVE_SCHEMA_VERSION
            ):
                raise ValueError
            draft = NarrativeDraft(
                request_id=context.request_id,
                execution_id=context.execution_id,
                generated_at=result.completed_at,
                **payload,
            )
        except (KeyError, TypeError, ValueError, ValidationError):
            error = NarrativeDraftNormalizationError("Narrative structured output is invalid")
            return self._failure(
                request,
                context,
                result.completed_at,
                NarrativeGenerationStatus.INVALID_OUTPUT,
                error,
                True,
                result.metrics,
            )
        validation = validate_narrative_draft(
            request.narrative_request, request.source_bundle, request.section_plan, draft
        )
        if not validation.valid:
            error = NarrativeGenerationSafeError(
                code="narrative_draft_structurally_invalid",
                safe_message="Narrative draft failed structural validation",
                retryable=True,
            )
            return NarrativeGenerationOutcome(
                generation_id=request.generation_id,
                request_id=context.request_id,
                execution_id=context.execution_id,
                provider_id=self._adapter.provider_id,
                status=NarrativeGenerationStatus.INVALID_OUTPUT,
                validation_result=validation,
                retryable=True,
                metrics=result.metrics,
                warnings=result.safe_warnings,
                started_at=context.started_at,
                completed_at=result.completed_at,
                error=error,
            )
        return NarrativeGenerationOutcome(
            generation_id=request.generation_id,
            request_id=context.request_id,
            execution_id=context.execution_id,
            provider_id=self._adapter.provider_id,
            status=NarrativeGenerationStatus.SUCCEEDED,
            draft=draft,
            validation_result=validation,
            metrics=result.metrics,
            warnings=result.safe_warnings,
            started_at=context.started_at,
            completed_at=result.completed_at,
        )

    @staticmethod
    def _validate_identity(request, context):
        narrative = request.narrative_request
        if (
            request.generation_id != context.generation_id
            or narrative.request_id != context.request_id
            or narrative.execution_id != context.execution_id
            or narrative.organization_id != context.organization_id
            or narrative.actor_id != context.actor_id
            or narrative.correlation_id != context.correlation_id
        ):
            raise NarrativeGenerationIdentityError(
                "Generation request and context identity mismatch"
            )
        try:
            require_not_lower(context.classification, request.expected_classification)
            require_not_lower(request.expected_classification, context.classification)
        except ValueError as exc:
            raise NarrativeGenerationClassificationError(
                "Generation context classification mismatch"
            ) from exc

    def _failure(self, request, context, completed, status, error, retryable=False, metrics=None):
        return NarrativeGenerationOutcome(
            generation_id=request.generation_id,
            request_id=context.request_id,
            execution_id=context.execution_id,
            provider_id=self._adapter.provider_id,
            status=status,
            retryable=retryable,
            metrics=metrics or NarrativeProviderMetrics(provider_call_count=0),
            started_at=context.started_at,
            completed_at=completed,
            error=NarrativeGenerationSafeError(
                code=error.code, safe_message=error.safe_message, retryable=retryable
            ),
        )
