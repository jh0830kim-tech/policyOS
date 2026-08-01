"""Immutable metadata-only observability contracts and bundle validation."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.execution.validation import require_aware, require_not_lower
from app.observability._base import ObservabilityModel
from app.observability.errors import (
    DeploymentStopSignalError,
    DuplicateObservationError,
    ObservabilityAuditMetadataError,
    ObservabilityBindingMismatchError,
    ObservabilityBundleError,
    ObservabilityClassificationError,
    ObservabilityOrderingError,
    ObservationCompletenessError,
    ObservationCorrelationError,
    ObservationEventError,
    ObservationRedactionError,
)
from app.zero_trust.quarantine import ExecutionCombinationIdentity, QuarantineScope


class ObservationCategory(StrEnum):
    IDENTITY = "identity"
    AUTHORIZATION = "authorization"
    EXECUTION = "execution"
    MODEL_SELECTION = "model_selection"
    PROVIDER_INVOCATION = "provider_invocation"
    MCP_OPERATION = "mcp_operation"
    CONNECTOR_OPERATION = "connector_operation"
    CROSS_VALIDATION = "cross_validation"
    SECRETARY_HANDOFF = "secretary_handoff"
    ZERO_TRUST = "zero_trust"
    CREDENTIAL_ACCESS = "credential_access"
    QUARANTINE = "quarantine"
    EVALUATION = "evaluation"
    AUDIT = "audit"
    GOVERNANCE = "governance"


class ObservationSeverity(StrEnum):
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ObservationOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    QUARANTINED = "quarantined"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN_RECORDED = "unknown_recorded"


class ObservationEventType(StrEnum):
    DELEGATION_CREATED = "delegation_created"
    AUTHORIZATION_ALLOWED = "authorization_allowed"
    AUTHORIZATION_DENIED = "authorization_denied"
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"
    TASK_PLANNED = "task_planned"
    TASK_STATE_CHANGED = "task_state_changed"
    EXECUTION_STATE_CHANGED = "execution_state_changed"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_CANCELLED = "execution_cancelled"
    MODEL_SELECTED = "model_selected"
    MODEL_INVOCATION_PERMITTED = "model_invocation_permitted"
    MODEL_INVOCATION_REJECTED = "model_invocation_rejected"
    PROVIDER_RESULT_RECORDED = "provider_result_recorded"
    MCP_REQUEST_AUTHORIZED = "mcp_request_authorized"
    MCP_REQUEST_DENIED = "mcp_request_denied"
    MCP_PROTOCOL_MISMATCH = "mcp_protocol_mismatch"
    MCP_TOOL_RESULT_RECORDED = "mcp_tool_result_recorded"
    CONNECTOR_OPERATION_AUTHORIZED = "connector_operation_authorized"
    CONNECTOR_OPERATION_DENIED = "connector_operation_denied"
    CROSS_VALIDATION_PLAN_CREATED = "cross_validation_plan_created"
    CROSS_VALIDATION_RUN_RECORDED = "cross_validation_run_recorded"
    CONSENSUS_RECORDED = "consensus_recorded"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    SECRET_ACCESS_GRANTED = "secret_access_granted"
    SECRET_ACCESS_DENIED = "secret_access_denied"
    SECURITY_VIOLATION_CONFIRMED = "security_violation_confirmed"
    QUARANTINE_APPLIED = "quarantine_applied"
    QUARANTINE_RELEASE_REQUESTED = "quarantine_release_requested"
    QUARANTINE_RELEASED = "quarantine_released"
    EVALUATION_PLAN_CREATED = "evaluation_plan_created"
    EVALUATION_EXECUTION_STATE_CHANGED = "evaluation_execution_state_changed"
    EVIDENCE_BUNDLE_CREATED = "evidence_bundle_created"
    EVIDENCE_VALIDATION_RECORDED = "evidence_validation_recorded"
    EVALUATION_PIPELINE_RECORDED = "evaluation_pipeline_recorded"
    AUDIT_RECORD_CREATED = "audit_record_created"
    AUDIT_COMPLETENESS_FAILED = "audit_completeness_failed"
    DEPLOYMENT_STOP_SIGNAL_RECORDED = "deployment_stop_signal_recorded"


class ObservationSubjectType(StrEnum):
    USER = "user"
    SERVICE_ACTOR = "service_actor"
    AGENT_INSTANCE = "agent_instance"
    TASK = "task"
    RESOURCE = "resource"
    MODEL = "model"
    PROVIDER = "provider"
    MCP_SERVER = "mcp_server"
    MCP_TOOL = "mcp_tool"
    CONNECTOR = "connector"
    CROSS_VALIDATION_PLAN = "cross_validation_plan"
    CROSS_VALIDATION_RUN = "cross_validation_run"
    SECRETARY_HANDOFF = "secretary_handoff"
    SECURITY_VIOLATION = "security_violation"
    QUARANTINE_DECISION = "quarantine_decision"
    EVALUATION_PLAN = "evaluation_plan"
    EVALUATION_EXECUTION = "evaluation_execution"
    EVIDENCE_BUNDLE = "evidence_bundle"
    VALIDATION_REPORT = "validation_report"
    EVALUATION_PIPELINE = "evaluation_pipeline"
    AUDIT_RECORD = "audit_record"
    DEPLOYMENT_STOP_SIGNAL = "deployment_stop_signal"


class ExcludedDataCategory(StrEnum):
    PROMPT_CONTENT = "prompt_content"
    DOCUMENT_CONTENT = "document_content"
    MODEL_OUTPUT_CONTENT = "model_output_content"
    MCP_PAYLOAD = "mcp_payload"
    CONNECTOR_PAYLOAD = "connector_payload"
    EVIDENCE_CONTENT = "evidence_content"
    HIDDEN_LABEL = "hidden_label"
    EXPECTED_OUTPUT = "expected_output"
    SECRET_VALUE = "secret_value"
    TOKEN_VALUE = "token_value"
    CREDENTIAL_VALUE = "credential_value"
    AUTHORIZATION_HEADER = "authorization_header"
    CHAIN_OF_THOUGHT = "chain_of_thought"
    PERSONAL_DATA_CONTENT = "personal_data_content"


class ObservationScope(StrEnum):
    EXECUTION = "execution"
    MODEL_AND_PROVIDER = "model_and_provider"
    MCP_AND_TOOL = "mcp_and_tool"
    CROSS_VALIDATION = "cross_validation"
    ZERO_TRUST = "zero_trust"
    EVALUATION_PIPELINE = "evaluation_pipeline"
    AUDIT_TRAIL = "audit_trail"
    DEPLOYMENT_STOP = "deployment_stop"


class ObservationCompletenessStatus(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    NOT_APPLICABLE = "not_applicable"


class DeploymentStopSignalStatus(StrEnum):
    RECORDED = "recorded"
    CONFIRMED = "confirmed"
    CLEARED_BY_SEPARATE_DECISION = "cleared_by_separate_decision"


def _canonical(value, field_name: str):
    if tuple(sorted(set(value), key=str)) != value:
        raise ObservabilityOrderingError(f"{field_name} must be canonical and unique")
    return value


def _aware(value, field_name: str):
    return require_aware(value, field_name)


def _not_lower(actual, required) -> None:
    try:
        require_not_lower(actual, required, field="observation classification")
    except ValueError as exc:
        raise ObservabilityClassificationError("observation classification downgrade") from exc


class ObservationCorrelationContext(ObservabilityModel):
    correlation_context_id: UUID
    correlation_id: str = Field(min_length=1, max_length=200)
    trace_reference_id: UUID | None = None
    parent_observation_id: UUID | None = None
    root_observation_id: UUID
    causation_observation_id: UUID | None = None
    tenant_id: UUID
    organization_id: UUID
    on_behalf_of_user_id: UUID
    service_actor_id: UUID
    agent_instance_id: UUID
    task_id: UUID
    resource_id: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=100)
    purpose: str = Field(min_length=1, max_length=100)
    risk_level: str = Field(min_length=1, max_length=50)
    classification: DataClassification
    delegation_lineage_id: UUID
    delegation_lineage_digest: str = Field(min_length=1, max_length=300)
    evaluation_plan_id: UUID | None = None
    evaluation_execution_id: UUID | None = None
    evaluation_pipeline_id: UUID | None = None
    cross_validation_plan_id: UUID | None = None
    cross_validation_run_id: UUID | None = None
    model_id: str | None = Field(default=None, max_length=200)
    provider_instance_id: str | None = Field(default=None, max_length=200)
    mcp_server_id: str | None = Field(default=None, max_length=200)
    tool_id: str | None = Field(default=None, max_length=200)
    connector_id: str | None = Field(default=None, max_length=200)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return _aware(value, "created_at")


class ObservationSubjectReference(ObservabilityModel):
    observation_subject_reference_id: UUID
    subject_type: ObservationSubjectType
    subject_id: str = Field(min_length=1, max_length=200)
    subject_version: str | None = Field(default=None, max_length=100)
    subject_revision: int | None = Field(default=None, ge=1)
    subject_schema_version: str = Field(min_length=1, max_length=100)
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return _aware(value, "created_at")


class ObservationEvent(ObservabilityModel):
    observation_event_id: UUID
    category: ObservationCategory
    event_type: ObservationEventType
    severity: ObservationSeverity
    outcome: ObservationOutcome
    correlation_context: ObservationCorrelationContext
    subject_reference: ObservationSubjectReference
    source_record_reference: str = Field(min_length=1, max_length=300)
    policy_revision: int | None = Field(default=None, ge=1)
    authorization_decision_id: UUID | None = None
    authorization_revision: int | None = Field(default=None, ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    reason_codes: tuple[str, ...]
    classification: DataClassification
    occurred_at: datetime
    recorded_at: datetime
    provider_instance_id: str | None = Field(default=None, max_length=200)
    model_id: str | None = Field(default=None, max_length=200)
    mcp_server_id: str | None = Field(default=None, max_length=200)
    protocol_version: str | None = Field(default=None, max_length=100)
    tool_id: str | None = Field(default=None, max_length=200)
    tool_schema_revision: str | None = Field(default=None, max_length=200)
    connector_id: str | None = Field(default=None, max_length=200)
    connector_operation: str | None = Field(default=None, max_length=100)

    @field_validator("reason_codes")
    @classmethod
    def canonical_reasons(cls, value):
        if not value:
            raise ObservationEventError("observation reason codes are required")
        return _canonical(value, "reason_codes")

    @field_validator("occurred_at", "recorded_at")
    @classmethod
    def aware(cls, value, info):
        return _aware(value, info.field_name)

    @model_validator(mode="after")
    def consistent(self):
        validate_observation_event(self)
        return self


def validate_observation_event(event: ObservationEvent) -> None:
    context = event.correlation_context
    subject = event.subject_reference
    if event.occurred_at > event.recorded_at:
        raise ObservationEventError("observation occurred after it was recorded")
    if context.parent_observation_id == event.observation_event_id:
        raise ObservationCorrelationError("observation cannot parent itself")
    if context.causation_observation_id == event.observation_event_id:
        raise ObservationCorrelationError("observation cannot cause itself")
    if (subject.tenant_id, subject.organization_id) != (
        context.tenant_id,
        context.organization_id,
    ):
        raise ObservationCorrelationError("observation subject scope mismatch")
    _not_lower(event.classification, context.classification)
    _not_lower(event.classification, subject.classification)
    _validate_event_category(event.category, event.event_type)


def _validate_event_category(
    category: ObservationCategory, event_type: ObservationEventType
) -> None:
    if event_type is ObservationEventType.DELEGATION_CREATED:
        expected = ObservationCategory.IDENTITY
    elif event_type in (
        ObservationEventType.AUTHORIZATION_ALLOWED,
        ObservationEventType.AUTHORIZATION_DENIED,
        ObservationEventType.APPROVAL_REQUIRED,
        ObservationEventType.APPROVAL_GRANTED,
        ObservationEventType.APPROVAL_REJECTED,
    ):
        expected = ObservationCategory.AUTHORIZATION
    elif event_type in (
        ObservationEventType.TASK_PLANNED,
        ObservationEventType.TASK_STATE_CHANGED,
        ObservationEventType.EXECUTION_STATE_CHANGED,
        ObservationEventType.EXECUTION_COMPLETED,
        ObservationEventType.EXECUTION_FAILED,
        ObservationEventType.EXECUTION_CANCELLED,
    ):
        expected = ObservationCategory.EXECUTION
    elif event_type in (
        ObservationEventType.MODEL_SELECTED,
        ObservationEventType.MODEL_INVOCATION_PERMITTED,
        ObservationEventType.MODEL_INVOCATION_REJECTED,
    ):
        expected = ObservationCategory.MODEL_SELECTION
    elif event_type is ObservationEventType.PROVIDER_RESULT_RECORDED:
        expected = ObservationCategory.PROVIDER_INVOCATION
    elif event_type.name.startswith("MCP_"):
        expected = ObservationCategory.MCP_OPERATION
    elif event_type.name.startswith("CONNECTOR_"):
        expected = ObservationCategory.CONNECTOR_OPERATION
    elif event_type in (
        ObservationEventType.CROSS_VALIDATION_PLAN_CREATED,
        ObservationEventType.CROSS_VALIDATION_RUN_RECORDED,
        ObservationEventType.CONSENSUS_RECORDED,
        ObservationEventType.MANUAL_REVIEW_REQUIRED,
    ):
        expected = ObservationCategory.CROSS_VALIDATION
    elif event_type in (
        ObservationEventType.SECRET_ACCESS_GRANTED,
        ObservationEventType.SECRET_ACCESS_DENIED,
    ):
        expected = ObservationCategory.CREDENTIAL_ACCESS
    elif event_type is ObservationEventType.SECURITY_VIOLATION_CONFIRMED:
        expected = ObservationCategory.ZERO_TRUST
    elif event_type.name.startswith("QUARANTINE_"):
        expected = ObservationCategory.QUARANTINE
    elif event_type.name.startswith("EVALUATION_") or event_type in (
        ObservationEventType.EVIDENCE_BUNDLE_CREATED,
        ObservationEventType.EVIDENCE_VALIDATION_RECORDED,
    ):
        expected = ObservationCategory.EVALUATION
    elif event_type in (
        ObservationEventType.AUDIT_RECORD_CREATED,
        ObservationEventType.AUDIT_COMPLETENESS_FAILED,
    ):
        expected = ObservationCategory.AUDIT
    else:
        expected = ObservationCategory.GOVERNANCE
    if category is not expected:
        raise ObservationEventError("observation category and event type mismatch")


class ObservationRedactionPolicyReference(ObservabilityModel):
    redaction_policy_reference_id: UUID
    tenant_id: UUID
    organization_id: UUID
    policy_name: str = Field(min_length=1, max_length=100)
    policy_version: str = Field(min_length=1, max_length=100)
    policy_revision: int = Field(ge=1)
    policy_document_reference: str = Field(min_length=1, max_length=300)
    classification: DataClassification
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return _aware(value, "created_at")


class ObservationRedactionDeclaration(ObservabilityModel):
    redaction_declaration_id: UUID
    observation_event_id: UUID
    redaction_policy_reference_id: UUID
    excluded_data_categories: tuple[ExcludedDataCategory, ...] = Field(min_length=1)
    declaration_revision: int = Field(ge=1)
    created_at: datetime

    @field_validator("excluded_data_categories")
    @classmethod
    def canonical_categories(cls, value):
        try:
            return _canonical(value, "excluded_data_categories")
        except ObservabilityOrderingError as exc:
            raise ObservationRedactionError(str(exc)) from exc

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return _aware(value, "created_at")


class ObservationCompletenessRequirement(ObservabilityModel):
    completeness_requirement_id: UUID
    tenant_id: UUID
    organization_id: UUID
    observation_scope: ObservationScope
    required_event_types: tuple[ObservationEventType, ...] = Field(min_length=1)
    required_categories: tuple[ObservationCategory, ...] = Field(min_length=1)
    policy_revision: int = Field(ge=1)
    requirement_revision: int = Field(ge=1)
    classification: DataClassification
    created_at: datetime

    @field_validator("required_event_types", "required_categories")
    @classmethod
    def canonical_required(cls, value, info):
        return _canonical(value, info.field_name)

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return _aware(value, "created_at")


class ObservationCompletenessAssessment(ObservabilityModel):
    completeness_assessment_id: UUID
    completeness_requirement_id: UUID
    correlation_id: str = Field(min_length=1, max_length=200)
    tenant_id: UUID
    organization_id: UUID
    observed_event_ids: tuple[UUID, ...]
    missing_event_types: tuple[ObservationEventType, ...]
    missing_categories: tuple[ObservationCategory, ...]
    status: ObservationCompletenessStatus
    reason_codes: tuple[str, ...] = Field(min_length=1)
    assessed_at: datetime

    @field_validator(
        "observed_event_ids", "missing_event_types", "missing_categories", "reason_codes"
    )
    @classmethod
    def canonical_values(cls, value, info):
        return _canonical(value, info.field_name)

    @field_validator("assessed_at")
    @classmethod
    def aware(cls, value):
        return _aware(value, "assessed_at")

    @model_validator(mode="after")
    def consistent(self):
        validate_completeness_assessment(self)
        return self


def validate_completeness_assessment(
    assessment: ObservationCompletenessAssessment,
) -> None:
    missing = bool(assessment.missing_event_types or assessment.missing_categories)
    if assessment.status is ObservationCompletenessStatus.COMPLETE and missing:
        raise ObservationCompletenessError("complete assessment contains missing facts")
    if assessment.status is ObservationCompletenessStatus.INCOMPLETE and not missing:
        raise ObservationCompletenessError("incomplete assessment requires missing facts")
    if assessment.status is ObservationCompletenessStatus.NOT_APPLICABLE and (
        assessment.observed_event_ids or missing
    ):
        raise ObservationCompletenessError(
            "not-applicable assessment cannot contain observed or missing facts"
        )


class DeploymentStopSignal(ObservabilityModel):
    deployment_stop_signal_id: UUID
    tenant_scope: UUID | None
    quarantine_scope: QuarantineScope
    execution_combination: ExecutionCombinationIdentity
    triggering_observation_event_ids: tuple[UUID, ...] = Field(min_length=1)
    security_violation_event_ids: tuple[UUID, ...]
    quarantine_decision_ids: tuple[UUID, ...]
    signal_reason_codes: tuple[str, ...] = Field(min_length=1)
    signal_status: DeploymentStopSignalStatus
    policy_revision: str = Field(min_length=1, max_length=200)
    classification: DataClassification
    clearing_governance_decision_reference: str | None = Field(default=None, max_length=300)
    created_at: datetime

    @field_validator(
        "triggering_observation_event_ids",
        "security_violation_event_ids",
        "quarantine_decision_ids",
        "signal_reason_codes",
    )
    @classmethod
    def canonical_values(cls, value, info):
        return _canonical(value, info.field_name)

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return _aware(value, "created_at")

    @model_validator(mode="after")
    def consistent(self):
        validate_deployment_stop_signal(self)
        return self


def validate_deployment_stop_signal(signal: DeploymentStopSignal) -> None:
    combination = signal.execution_combination
    if (signal.tenant_scope, signal.quarantine_scope) != (
        combination.tenant_scope,
        combination.quarantine_scope,
    ):
        raise DeploymentStopSignalError("deployment-stop signal scope mismatch")
    cleared = signal.signal_status is DeploymentStopSignalStatus.CLEARED_BY_SEPARATE_DECISION
    if cleared != (signal.clearing_governance_decision_reference is not None):
        raise DeploymentStopSignalError(
            "deployment-stop clearing requires a separate decision reference"
        )


class ObservabilityBundleVersion(ObservabilityModel):
    observability_bundle_version: str = Field(min_length=1, max_length=100)
    observability_contract_version: str = Field(min_length=1, max_length=100)
    observability_schema_version: str = Field(min_length=1, max_length=100)


class ObservabilityBundleAuditMetadata(ObservabilityModel):
    observability_bundle_id: UUID
    observability_bundle_version: str = Field(min_length=1, max_length=100)
    correlation_id: str = Field(min_length=1, max_length=200)
    event_count: int = Field(ge=1)
    category_count: int = Field(ge=1)
    critical_event_count: int = Field(ge=0)
    incomplete_assessment_count: int = Field(ge=0)
    deployment_stop_signal_count: int = Field(ge=0)
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return _aware(value, "created_at")


class ObservabilityBundle(ObservabilityModel):
    observability_bundle_id: UUID
    observability_bundle_version: ObservabilityBundleVersion
    correlation_context: ObservationCorrelationContext
    observation_events: tuple[ObservationEvent, ...] = Field(min_length=1)
    redaction_declarations: tuple[ObservationRedactionDeclaration, ...]
    completeness_assessments: tuple[ObservationCompletenessAssessment, ...]
    deployment_stop_signals: tuple[DeploymentStopSignal, ...]
    audit_metadata: ObservabilityBundleAuditMetadata | None = None
    classification: DataClassification
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return _aware(value, "created_at")

    @model_validator(mode="after")
    def consistent(self):
        validate_observability_bundle(self)
        return self


class ObservabilityBundleRequest(ObservabilityModel):
    observability_bundle_id: UUID
    observability_bundle_version: ObservabilityBundleVersion
    correlation_context: ObservationCorrelationContext
    observation_events: tuple[ObservationEvent, ...] = Field(min_length=1)
    redaction_declarations: tuple[ObservationRedactionDeclaration, ...]
    completeness_assessments: tuple[ObservationCompletenessAssessment, ...]
    deployment_stop_signals: tuple[DeploymentStopSignal, ...]
    audit_metadata: ObservabilityBundleAuditMetadata | None = None
    classification: DataClassification
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return _aware(value, "created_at")


def _validate_event_collection(bundle: ObservabilityBundle) -> None:
    events = bundle.observation_events
    event_ids = tuple(item.observation_event_id for item in events)
    if len(event_ids) != len(set(event_ids)):
        raise DuplicateObservationError("duplicate observation event identity")
    keys = tuple((item.occurred_at, item.observation_event_id) for item in events)
    if keys != tuple(sorted(keys)):
        raise ObservabilityOrderingError("observation events are not canonical")
    context = bundle.correlation_context
    for event in events:
        candidate = event.correlation_context
        if (
            candidate.correlation_id,
            candidate.root_observation_id,
            candidate.tenant_id,
            candidate.organization_id,
            candidate.on_behalf_of_user_id,
            candidate.service_actor_id,
            candidate.agent_instance_id,
            candidate.task_id,
            candidate.resource_id,
            candidate.action,
            candidate.purpose,
            candidate.risk_level,
            candidate.delegation_lineage_id,
            candidate.delegation_lineage_digest,
        ) != (
            context.correlation_id,
            context.root_observation_id,
            context.tenant_id,
            context.organization_id,
            context.on_behalf_of_user_id,
            context.service_actor_id,
            context.agent_instance_id,
            context.task_id,
            context.resource_id,
            context.action,
            context.purpose,
            context.risk_level,
            context.delegation_lineage_id,
            context.delegation_lineage_digest,
        ):
            raise ObservabilityBindingMismatchError("observation correlation mismatch")
        _not_lower(bundle.classification, event.classification)
        parent = candidate.parent_observation_id
        if parent is not None and parent not in event_ids:
            raise ObservationCorrelationError("observation parent is unknown")
    by_id = {item.observation_event_id: item for item in events}
    for event in events:
        parent = event.correlation_context.parent_observation_id
        if (
            parent is not None
            and by_id[parent].correlation_context.parent_observation_id
            == event.observation_event_id
        ):
            raise ObservationCorrelationError("local observation parent cycle")


def _validate_bundle_links(bundle: ObservabilityBundle) -> None:
    event_ids = {item.observation_event_id for item in bundle.observation_events}
    by_id = {item.observation_event_id: item for item in bundle.observation_events}
    declaration_ids = tuple(item.redaction_declaration_id for item in bundle.redaction_declarations)
    assessment_ids = tuple(
        item.completeness_assessment_id for item in bundle.completeness_assessments
    )
    signal_ids = tuple(item.deployment_stop_signal_id for item in bundle.deployment_stop_signals)
    for values in (declaration_ids, assessment_ids, signal_ids):
        if len(values) != len(set(values)):
            raise DuplicateObservationError("duplicate observability bundle identity")
    for declaration in bundle.redaction_declarations:
        if declaration.observation_event_id not in event_ids:
            raise ObservationRedactionError("redaction declaration event is unknown")
    context = bundle.correlation_context
    for assessment in bundle.completeness_assessments:
        if (
            assessment.correlation_id != context.correlation_id
            or assessment.tenant_id != context.tenant_id
            or assessment.organization_id != context.organization_id
            or not set(assessment.observed_event_ids).issubset(event_ids)
        ):
            raise ObservationCompletenessError("completeness assessment binding mismatch")
    for signal in bundle.deployment_stop_signals:
        if not set(signal.triggering_observation_event_ids).issubset(event_ids):
            raise DeploymentStopSignalError("deployment-stop trigger is unknown")
        for event_id in signal.triggering_observation_event_ids:
            _not_lower(signal.classification, by_id[event_id].classification)
        _not_lower(bundle.classification, signal.classification)


def _validate_bundle_audit(bundle: ObservabilityBundle) -> None:
    audit = bundle.audit_metadata
    if audit is None:
        return
    context = bundle.correlation_context
    actual = (
        audit.observability_bundle_id,
        audit.observability_bundle_version,
        audit.correlation_id,
        audit.event_count,
        audit.category_count,
        audit.critical_event_count,
        audit.incomplete_assessment_count,
        audit.deployment_stop_signal_count,
        audit.tenant_id,
        audit.organization_id,
        audit.classification,
        audit.created_at,
    )
    expected = (
        bundle.observability_bundle_id,
        bundle.observability_bundle_version.observability_bundle_version,
        context.correlation_id,
        len(bundle.observation_events),
        len({item.category for item in bundle.observation_events}),
        sum(item.severity is ObservationSeverity.CRITICAL for item in bundle.observation_events),
        sum(
            item.status is ObservationCompletenessStatus.INCOMPLETE
            for item in bundle.completeness_assessments
        ),
        len(bundle.deployment_stop_signals),
        context.tenant_id,
        context.organization_id,
        bundle.classification,
        bundle.created_at,
    )
    if actual != expected:
        raise ObservabilityAuditMetadataError("observability audit metadata mismatch")


def validate_observability_bundle(bundle: ObservabilityBundle) -> None:
    _validate_event_collection(bundle)
    _validate_bundle_links(bundle)
    context = bundle.correlation_context
    _not_lower(bundle.classification, context.classification)
    timestamps = (
        *(item.recorded_at for item in bundle.observation_events),
        *(item.created_at for item in bundle.redaction_declarations),
        *(item.assessed_at for item in bundle.completeness_assessments),
        *(item.created_at for item in bundle.deployment_stop_signals),
    )
    if any(item > bundle.created_at for item in timestamps):
        raise ObservabilityBundleError("observability component follows bundle creation")
    _validate_bundle_audit(bundle)


def build_observability_bundle(request: ObservabilityBundleRequest) -> ObservabilityBundle:
    return ObservabilityBundle(
        observability_bundle_id=request.observability_bundle_id,
        observability_bundle_version=request.observability_bundle_version,
        correlation_context=request.correlation_context,
        observation_events=request.observation_events,
        redaction_declarations=request.redaction_declarations,
        completeness_assessments=request.completeness_assessments,
        deployment_stop_signals=request.deployment_stop_signals,
        audit_metadata=request.audit_metadata,
        classification=request.classification,
        created_at=request.created_at,
    )
