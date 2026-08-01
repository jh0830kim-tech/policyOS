"""Pure exact bindings from observation metadata to immutable source records."""

from app.ai_providers.domain import ProviderInvocationAuditRecord
from app.ai_selection.invocation import AuthorizedInvocationPermit
from app.cross_validation.consensus import ConsensusDecisionPackage
from app.cross_validation.domain import CrossValidationPlan, CrossValidationRunCollection
from app.cross_validation.secretary_handoff import CrossValidationSecretaryHandoff
from app.evaluation.evidence import EvaluationEvidenceBundle
from app.evaluation.execution_state import EvaluationExecutionRecord
from app.evaluation.pipeline import EvaluationPipelineRecord
from app.evaluation.planning import EvaluationPlan
from app.evaluation.validation import EvaluationEvidenceValidationReport
from app.execution.validation import require_not_lower
from app.mcp_governance.authorization import (
    AuthorizedMcpToolInvocationPermit,
    McpToolAuthorizationDecision,
)
from app.mcp_governance.cross_validation import McpToolRunResultReference
from app.observability.domain import (
    DeploymentStopSignal,
    ObservationCompletenessAssessment,
    ObservationCompletenessStatus,
    ObservationEvent,
    ObservationEventType,
    ObservationSubjectType,
)
from app.observability.errors import ObservabilityBindingMismatchError
from app.zero_trust.credentials import SecretAccessAuditRecord
from app.zero_trust.quarantine import (
    QuarantineDecision,
    QuarantineDecisionOutcome,
    SecurityViolationEvent,
)


def _bind(
    event: ObservationEvent,
    *,
    kind: str,
    source_id,
    subject_type: ObservationSubjectType,
    event_type: ObservationEventType,
) -> None:
    if (
        event.source_record_reference != f"{kind}://{source_id}"
        or event.subject_reference.subject_type is not subject_type
        or event.subject_reference.subject_id != str(source_id)
        or event.event_type is not event_type
    ):
        raise ObservabilityBindingMismatchError("observation source identity mismatch")


def _scope(event: ObservationEvent, tenant_id, organization_id=None) -> None:
    context = event.correlation_context
    if context.tenant_id != tenant_id or (
        organization_id is not None and context.organization_id != organization_id
    ):
        raise ObservabilityBindingMismatchError("observation source scope mismatch")


def _classification(event: ObservationEvent, source_classification) -> None:
    try:
        require_not_lower(
            event.classification,
            source_classification,
            field="observation source classification",
        )
    except ValueError as exc:
        raise ObservabilityBindingMismatchError(
            "observation source classification downgrade"
        ) from exc


def validate_evaluation_plan_observation(event: ObservationEvent, source: EvaluationPlan) -> None:
    _bind(
        event,
        kind="evaluation-plan",
        source_id=source.evaluation_plan_id,
        subject_type=ObservationSubjectType.EVALUATION_PLAN,
        event_type=ObservationEventType.EVALUATION_PLAN_CREATED,
    )
    _scope(event, source.tenant_id, source.organization_id)
    if event.correlation_context.evaluation_plan_id != source.evaluation_plan_id:
        raise ObservabilityBindingMismatchError("evaluation plan correlation mismatch")


def validate_evaluation_execution_observation(
    event: ObservationEvent, source: EvaluationExecutionRecord
) -> None:
    _bind(
        event,
        kind="evaluation-execution",
        source_id=source.evaluation_execution_id,
        subject_type=ObservationSubjectType.EVALUATION_EXECUTION,
        event_type=ObservationEventType.EVALUATION_EXECUTION_STATE_CHANGED,
    )
    context = source.execution_context
    _scope(event, context.tenant_id, context.organization_id)
    if event.correlation_context.evaluation_execution_id != source.evaluation_execution_id:
        raise ObservabilityBindingMismatchError("evaluation execution correlation mismatch")


def validate_evidence_bundle_observation(
    event: ObservationEvent, source: EvaluationEvidenceBundle
) -> None:
    _bind(
        event,
        kind="evaluation-evidence",
        source_id=source.evidence_bundle_id,
        subject_type=ObservationSubjectType.EVIDENCE_BUNDLE,
        event_type=ObservationEventType.EVIDENCE_BUNDLE_CREATED,
    )
    _scope(event, source.provenance.tenant_id, source.provenance.organization_id)
    if (
        event.correlation_context.evaluation_plan_id != source.evaluation_plan_id
        or event.correlation_context.evaluation_execution_id != source.evaluation_execution_id
    ):
        raise ObservabilityBindingMismatchError("evidence correlation mismatch")


def validate_validation_report_observation(
    event: ObservationEvent, source: EvaluationEvidenceValidationReport
) -> None:
    _bind(
        event,
        kind="evaluation-validation",
        source_id=source.report_id,
        subject_type=ObservationSubjectType.VALIDATION_REPORT,
        event_type=ObservationEventType.EVIDENCE_VALIDATION_RECORDED,
    )
    context = event.correlation_context
    if (
        context.evaluation_plan_id != source.plan_id
        or context.evaluation_execution_id != source.execution_id
    ):
        raise ObservabilityBindingMismatchError("validation report correlation mismatch")


def validate_evaluation_pipeline_observation(
    event: ObservationEvent, source: EvaluationPipelineRecord
) -> None:
    _bind(
        event,
        kind="evaluation-pipeline",
        source_id=source.pipeline_id,
        subject_type=ObservationSubjectType.EVALUATION_PIPELINE,
        event_type=ObservationEventType.EVALUATION_PIPELINE_RECORDED,
    )
    _scope(event, source.tenant_id, source.organization_id)
    context = event.correlation_context
    if (
        context.evaluation_pipeline_id != source.pipeline_id
        or context.evaluation_plan_id != source.evaluation_plan_id
        or context.evaluation_execution_id != source.evaluation_execution_id
    ):
        raise ObservabilityBindingMismatchError("evaluation pipeline correlation mismatch")


def validate_security_violation_observation(
    event: ObservationEvent, source: SecurityViolationEvent
) -> None:
    _bind(
        event,
        kind="security-violation",
        source_id=source.violation_event_id,
        subject_type=ObservationSubjectType.SECURITY_VIOLATION,
        event_type=ObservationEventType.SECURITY_VIOLATION_CONFIRMED,
    )
    _scope(event, source.tenant_id, source.organization_id)
    _classification(event, source.classification)
    if not source.confirmed:
        raise ObservabilityBindingMismatchError("security violation is not confirmed")


def validate_quarantine_decision_observation(
    event: ObservationEvent, source: QuarantineDecision
) -> None:
    _bind(
        event,
        kind="quarantine-decision",
        source_id=source.quarantine_decision_id,
        subject_type=ObservationSubjectType.QUARANTINE_DECISION,
        event_type=ObservationEventType.QUARANTINE_APPLIED,
    )
    if source.outcome not in (
        QuarantineDecisionOutcome.QUARANTINE,
        QuarantineDecisionOutcome.EXTEND_QUARANTINE,
    ):
        raise ObservabilityBindingMismatchError("quarantine was not applied")
    if (
        source.tenant_scope is not None
        and event.correlation_context.tenant_id != source.tenant_scope
    ):
        raise ObservabilityBindingMismatchError("quarantine tenant mismatch")


def validate_mcp_authorization_observation(
    event: ObservationEvent, source: McpToolAuthorizationDecision
) -> None:
    if source.outcome.value == "allow":
        expected = ObservationEventType.MCP_REQUEST_AUTHORIZED
    elif source.outcome.value == "deny":
        expected = ObservationEventType.MCP_REQUEST_DENIED
    else:
        expected = ObservationEventType.APPROVAL_REQUIRED
    _bind(
        event,
        kind="mcp-authorization",
        source_id=source.decision_id,
        subject_type=ObservationSubjectType.MCP_TOOL,
        event_type=expected,
    )
    _scope(event, source.tenant_id)
    _classification(event, source.classification)
    if (
        event.mcp_server_id != source.mcp_server_id
        or event.tool_id != source.tool_id
        or event.protocol_version != source.protocol_version
        or event.tool_schema_revision != source.tool_schema_revision
    ):
        raise ObservabilityBindingMismatchError("MCP observation binding mismatch")


def validate_mcp_permit_observation(
    event: ObservationEvent, source: AuthorizedMcpToolInvocationPermit
) -> None:
    _bind(
        event,
        kind="mcp-permit",
        source_id=source.permit_id,
        subject_type=ObservationSubjectType.MCP_TOOL,
        event_type=ObservationEventType.MCP_REQUEST_AUTHORIZED,
    )
    _scope(event, source.tenant_id)
    _classification(event, source.classification)
    if (
        event.mcp_server_id != source.mcp_server_id
        or event.tool_id != source.tool_id
        or event.protocol_version != source.protocol_version
        or event.tool_schema_revision != source.tool_schema_revision
    ):
        raise ObservabilityBindingMismatchError("MCP permit observation mismatch")


def validate_mcp_result_observation(
    event: ObservationEvent, source: McpToolRunResultReference
) -> None:
    _bind(
        event,
        kind="mcp-result",
        source_id=source.tool_result_id,
        subject_type=ObservationSubjectType.MCP_TOOL,
        event_type=ObservationEventType.MCP_TOOL_RESULT_RECORDED,
    )
    _classification(event, source.classification)
    if (
        event.mcp_server_id != source.mcp_server_id
        or event.tool_id != source.tool_id
        or event.protocol_version != source.protocol_version
        or event.tool_schema_revision != source.tool_schema_revision
    ):
        raise ObservabilityBindingMismatchError("MCP result observation mismatch")


def validate_model_permit_observation(
    event: ObservationEvent, source: AuthorizedInvocationPermit
) -> None:
    _bind(
        event,
        kind="model-permit",
        source_id=source.permit_id,
        subject_type=ObservationSubjectType.MODEL,
        event_type=ObservationEventType.MODEL_INVOCATION_PERMITTED,
    )
    _scope(event, source.tenant_id)
    _classification(event, source.classification)
    if (
        event.model_id != source.model_id
        or event.provider_instance_id != source.provider_instance_id
    ):
        raise ObservabilityBindingMismatchError("model permit observation mismatch")


def validate_provider_audit_observation(
    event: ObservationEvent, source: ProviderInvocationAuditRecord
) -> None:
    _bind(
        event,
        kind="provider-audit",
        source_id=source.audit_id,
        subject_type=ObservationSubjectType.PROVIDER,
        event_type=ObservationEventType.PROVIDER_RESULT_RECORDED,
    )
    if (
        event.model_id != source.model_id
        or event.provider_instance_id != source.provider_instance_id
        or event.registry_revision != source.registry_revision
    ):
        raise ObservabilityBindingMismatchError("provider audit observation mismatch")


def validate_cross_validation_plan_observation(
    event: ObservationEvent, source: CrossValidationPlan
) -> None:
    _bind(
        event,
        kind="cross-validation-plan",
        source_id=source.plan_id,
        subject_type=ObservationSubjectType.CROSS_VALIDATION_PLAN,
        event_type=ObservationEventType.CROSS_VALIDATION_PLAN_CREATED,
    )
    _scope(event, source.tenant_id)
    _classification(event, source.classification)
    if event.correlation_context.cross_validation_plan_id != source.plan_id:
        raise ObservabilityBindingMismatchError("cross-validation plan mismatch")


def validate_cross_validation_run_observation(
    event: ObservationEvent, source: CrossValidationRunCollection
) -> None:
    _bind(
        event,
        kind="cross-validation-run",
        source_id=source.collection_id,
        subject_type=ObservationSubjectType.CROSS_VALIDATION_RUN,
        event_type=ObservationEventType.CROSS_VALIDATION_RUN_RECORDED,
    )
    _scope(event, source.tenant_id)
    context = event.correlation_context
    if (
        context.cross_validation_plan_id != source.plan_id
        or context.cross_validation_run_id != source.collection_id
    ):
        raise ObservabilityBindingMismatchError("cross-validation run mismatch")


def validate_consensus_observation(
    event: ObservationEvent, source: ConsensusDecisionPackage
) -> None:
    _bind(
        event,
        kind="consensus",
        source_id=source.package_id,
        subject_type=ObservationSubjectType.CROSS_VALIDATION_RUN,
        event_type=ObservationEventType.CONSENSUS_RECORDED,
    )
    if (
        event.correlation_context.cross_validation_plan_id
        != source.assessment_specification.plan_id
    ):
        raise ObservabilityBindingMismatchError("consensus observation mismatch")
    _classification(event, source.effective_classification)


def validate_secretary_handoff_observation(
    event: ObservationEvent, source: CrossValidationSecretaryHandoff
) -> None:
    _bind(
        event,
        kind="secretary-handoff",
        source_id=source.handoff_id,
        subject_type=ObservationSubjectType.SECRETARY_HANDOFF,
        event_type=ObservationEventType.MANUAL_REVIEW_REQUIRED,
    )
    _scope(event, source.tenant_id)
    _classification(event, source.effective_classification)
    if event.correlation_context.cross_validation_plan_id != source.plan_id:
        raise ObservabilityBindingMismatchError("Secretary handoff mismatch")


def validate_secret_access_observation(
    event: ObservationEvent, source: SecretAccessAuditRecord
) -> None:
    expected = (
        ObservationEventType.SECRET_ACCESS_GRANTED
        if source.access_result.value == "allowed"
        else ObservationEventType.SECRET_ACCESS_DENIED
    )
    _bind(
        event,
        kind="secret-access-audit",
        source_id=source.audit_id,
        subject_type=ObservationSubjectType.AUDIT_RECORD,
        event_type=expected,
    )
    _scope(event, source.tenant_id, source.organization_id)


ObservationSource = (
    EvaluationPlan
    | EvaluationExecutionRecord
    | EvaluationEvidenceBundle
    | EvaluationEvidenceValidationReport
    | EvaluationPipelineRecord
    | SecurityViolationEvent
    | QuarantineDecision
    | McpToolAuthorizationDecision
    | AuthorizedMcpToolInvocationPermit
    | McpToolRunResultReference
    | AuthorizedInvocationPermit
    | ProviderInvocationAuditRecord
    | CrossValidationPlan
    | CrossValidationRunCollection
    | ConsensusDecisionPackage
    | CrossValidationSecretaryHandoff
    | SecretAccessAuditRecord
)


def validate_observation_source_binding(event: ObservationEvent, source: ObservationSource) -> None:
    validators = (
        (EvaluationPlan, validate_evaluation_plan_observation),
        (EvaluationExecutionRecord, validate_evaluation_execution_observation),
        (EvaluationEvidenceBundle, validate_evidence_bundle_observation),
        (EvaluationEvidenceValidationReport, validate_validation_report_observation),
        (EvaluationPipelineRecord, validate_evaluation_pipeline_observation),
        (SecurityViolationEvent, validate_security_violation_observation),
        (QuarantineDecision, validate_quarantine_decision_observation),
        (McpToolAuthorizationDecision, validate_mcp_authorization_observation),
        (AuthorizedMcpToolInvocationPermit, validate_mcp_permit_observation),
        (McpToolRunResultReference, validate_mcp_result_observation),
        (AuthorizedInvocationPermit, validate_model_permit_observation),
        (ProviderInvocationAuditRecord, validate_provider_audit_observation),
        (CrossValidationPlan, validate_cross_validation_plan_observation),
        (CrossValidationRunCollection, validate_cross_validation_run_observation),
        (ConsensusDecisionPackage, validate_consensus_observation),
        (CrossValidationSecretaryHandoff, validate_secretary_handoff_observation),
        (SecretAccessAuditRecord, validate_secret_access_observation),
    )
    for source_type, validator in validators:
        if isinstance(source, source_type):
            validator(event, source)
            return
    raise ObservabilityBindingMismatchError("unsupported observation source type")


def validate_audit_quarantine_linkage(
    assessment: ObservationCompletenessAssessment,
    audit_event: ObservationEvent,
    *,
    security_violation: SecurityViolationEvent | None = None,
    quarantine_decision: QuarantineDecision | None = None,
    deployment_stop_signal: DeploymentStopSignal | None = None,
) -> None:
    if (
        assessment.status is not ObservationCompletenessStatus.INCOMPLETE
        or audit_event.event_type is not ObservationEventType.AUDIT_COMPLETENESS_FAILED
        or audit_event.correlation_context.correlation_id != assessment.correlation_id
        or audit_event.correlation_context.tenant_id != assessment.tenant_id
        or audit_event.correlation_context.organization_id != assessment.organization_id
    ):
        raise ObservabilityBindingMismatchError("audit completeness linkage mismatch")
    if security_violation is not None:
        if (
            security_violation.violation_event_id
            not in (
                deployment_stop_signal.security_violation_event_ids
                if deployment_stop_signal is not None
                else (security_violation.violation_event_id,)
            )
            or security_violation.tenant_id != assessment.tenant_id
        ):
            raise ObservabilityBindingMismatchError("security violation linkage mismatch")
    if quarantine_decision is not None:
        if security_violation is None or (
            quarantine_decision.violation_event_id != security_violation.violation_event_id
        ):
            raise ObservabilityBindingMismatchError("quarantine decision linkage mismatch")
        if deployment_stop_signal is not None and (
            quarantine_decision.quarantine_decision_id
            not in deployment_stop_signal.quarantine_decision_ids
        ):
            raise ObservabilityBindingMismatchError("deployment-stop quarantine mismatch")
    if deployment_stop_signal is not None and (
        audit_event.observation_event_id
        not in deployment_stop_signal.triggering_observation_event_ids
    ):
        raise ObservabilityBindingMismatchError("deployment-stop audit trigger mismatch")
