"""Sprint 13 CP3 immutable observability-domain tests."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.evaluation import build_evaluation_pipeline_record
from app.observability import (
    DeploymentStopSignal,
    DeploymentStopSignalStatus,
    ExcludedDataCategory,
    ObservabilityBindingMismatchError,
    ObservabilityBundleAuditMetadata,
    ObservabilityBundleRequest,
    ObservabilityBundleVersion,
    ObservationCategory,
    ObservationCompletenessAssessment,
    ObservationCompletenessRequirement,
    ObservationCompletenessStatus,
    ObservationCorrelationContext,
    ObservationEvent,
    ObservationEventType,
    ObservationOutcome,
    ObservationRedactionDeclaration,
    ObservationRedactionPolicyReference,
    ObservationScope,
    ObservationSeverity,
    ObservationSubjectReference,
    ObservationSubjectType,
    build_observability_bundle,
    validate_audit_quarantine_linkage,
    validate_evaluation_pipeline_observation,
    validate_quarantine_decision_observation,
    validate_security_violation_observation,
)
from app.zero_trust import (
    ExecutionCombinationIdentity,
    QuarantineDecision,
    QuarantineDecisionOutcome,
    QuarantineScope,
    QuarantineTriggerType,
    SecurityViolationEvent,
    SecurityViolationSeverity,
)
from tests.test_evaluation_pipeline import pipeline_values
from tests.test_evaluation_planner import uid

NOW = datetime(2026, 8, 1, 10, tzinfo=UTC)


def context(event_id=None, **updates):
    event_id = event_id or uid(2000)
    values = dict(
        correlation_context_id=uid(2001),
        correlation_id="correlation-1",
        root_observation_id=uid(2000),
        tenant_id=uid(1),
        organization_id=uid(2),
        on_behalf_of_user_id=uid(3),
        service_actor_id=uid(4),
        agent_instance_id=uid(5),
        task_id=uid(6),
        resource_id="resource-1",
        action="observe",
        purpose="governance",
        risk_level="low",
        classification=DataClassification.CONFIDENTIAL,
        delegation_lineage_id=uid(7),
        delegation_lineage_digest="lineage-digest-reference",
        created_at=NOW,
    )
    values.update(updates)
    return ObservationCorrelationContext(**values)


def event(event_id=None, occurred_at=NOW, **updates):
    event_id = event_id or uid(2000)
    correlation = updates.pop("correlation_context", context(event_id))
    subject = updates.pop(
        "subject_reference",
        ObservationSubjectReference(
            observation_subject_reference_id=uid(2010),
            subject_type=ObservationSubjectType.RESOURCE,
            subject_id="resource-1",
            subject_schema_version="subject-v1",
            tenant_id=correlation.tenant_id,
            organization_id=correlation.organization_id,
            classification=DataClassification.CONFIDENTIAL,
            created_at=NOW,
        ),
    )
    values = dict(
        observation_event_id=event_id,
        category=ObservationCategory.AUDIT,
        event_type=ObservationEventType.AUDIT_RECORD_CREATED,
        severity=ObservationSeverity.INFO,
        outcome=ObservationOutcome.SUCCEEDED,
        correlation_context=correlation,
        subject_reference=subject,
        source_record_reference=f"audit://{event_id}",
        reason_codes=("recorded",),
        classification=DataClassification.CONFIDENTIAL,
        occurred_at=occurred_at,
        recorded_at=occurred_at,
    )
    values.update(updates)
    return ObservationEvent(**values)


def bundle_request(*, events=None, declarations=(), assessments=(), signals=(), audit=True):
    events = events or (event(),)
    bundle_time = max(item.recorded_at for item in events) + timedelta(minutes=1)
    version = ObservabilityBundleVersion(
        observability_bundle_version="bundle-v1",
        observability_contract_version="contract-v1",
        observability_schema_version="schema-v1",
    )
    metadata = ObservabilityBundleAuditMetadata(
        observability_bundle_id=uid(2100),
        observability_bundle_version="bundle-v1",
        correlation_id="correlation-1",
        event_count=len(events),
        category_count=len({item.category for item in events}),
        critical_event_count=sum(item.severity is ObservationSeverity.CRITICAL for item in events),
        incomplete_assessment_count=sum(
            item.status is ObservationCompletenessStatus.INCOMPLETE for item in assessments
        ),
        deployment_stop_signal_count=len(signals),
        tenant_id=uid(1),
        organization_id=uid(2),
        classification=DataClassification.CONFIDENTIAL,
        created_at=bundle_time,
    )
    return ObservabilityBundleRequest(
        observability_bundle_id=uid(2100),
        observability_bundle_version=version,
        correlation_context=events[0].correlation_context,
        observation_events=events,
        redaction_declarations=declarations,
        completeness_assessments=assessments,
        deployment_stop_signals=signals,
        audit_metadata=metadata if audit else None,
        classification=DataClassification.CONFIDENTIAL,
        created_at=bundle_time,
    )


def test_event_is_strict_frozen_and_metadata_only() -> None:
    value = event()
    with pytest.raises(ValidationError):
        value.outcome = ObservationOutcome.FAILED
    with pytest.raises(ValidationError):
        ObservationEvent(**{**value.model_dump(), "payload": "forbidden"})
    with pytest.raises(ValidationError):
        ObservationEvent(**{**value.model_dump(), "severity": 1})


def test_caller_values_and_aware_timestamps_are_required() -> None:
    value = event()
    assert value.observation_event_id == uid(2000)
    assert value.occurred_at is NOW
    with pytest.raises(ValidationError):
        context(created_at=NOW.replace(tzinfo=None))


def test_event_time_reason_category_and_self_reference_fail_closed() -> None:
    with pytest.raises(ValidationError):
        event(recorded_at=NOW - timedelta(seconds=1))
    with pytest.raises(ValidationError):
        event(reason_codes=("z", "a"))
    with pytest.raises(ValidationError):
        event(category=ObservationCategory.EXECUTION)
    with pytest.raises(ValidationError):
        event(correlation_context=context(parent_observation_id=uid(2000)))
    with pytest.raises(ValidationError):
        event(correlation_context=context(causation_observation_id=uid(2000)))


def test_subject_scope_and_classification_downgrade_are_rejected() -> None:
    wrong = event().subject_reference.model_copy(update={"tenant_id": uid(99)})
    with pytest.raises(ValidationError):
        event(subject_reference=wrong)
    with pytest.raises(ValidationError, match="classification downgrade"):
        event(classification=DataClassification.INTERNAL)


def test_closed_enums_and_no_runtime_event_types() -> None:
    with pytest.raises(ValidationError):
        ObservationEvent(**{**event().model_dump(), "event_type": "cpu_usage"})
    assert ObservationOutcome.UNKNOWN_RECORDED.value == "unknown_recorded"


def declaration(event_id=None, categories=None):
    event_id = event_id or uid(2000)
    categories = categories or tuple(sorted(ExcludedDataCategory, key=str))
    return ObservationRedactionDeclaration(
        redaction_declaration_id=uid(2200),
        observation_event_id=event_id,
        redaction_policy_reference_id=uid(2201),
        excluded_data_categories=categories,
        declaration_revision=1,
        created_at=NOW,
    )


def assessment(status=ObservationCompletenessStatus.COMPLETE, **updates):
    values = dict(
        completeness_assessment_id=uid(2300),
        completeness_requirement_id=uid(2301),
        correlation_id="correlation-1",
        tenant_id=uid(1),
        organization_id=uid(2),
        observed_event_ids=(uid(2000),),
        missing_event_types=(),
        missing_categories=(),
        status=status,
        reason_codes=("assessed",),
        assessed_at=NOW,
    )
    values.update(updates)
    return ObservationCompletenessAssessment(**values)


def test_redaction_declaration_is_canonical_metadata_only() -> None:
    value = declaration()
    assert set(value.excluded_data_categories) == set(ExcludedDataCategory)
    with pytest.raises(ValidationError):
        declaration(categories=tuple(reversed(value.excluded_data_categories)))
    with pytest.raises(ValidationError):
        declaration(categories=(ExcludedDataCategory.PROMPT_CONTENT,) * 2)


def test_redaction_policy_and_completeness_requirement_are_references_only() -> None:
    policy = ObservationRedactionPolicyReference(
        redaction_policy_reference_id=uid(2250),
        tenant_id=uid(1),
        organization_id=uid(2),
        policy_name="metadata-only",
        policy_version="v1",
        policy_revision=1,
        policy_document_reference="policy://redaction/1",
        classification=DataClassification.CONFIDENTIAL,
        created_at=NOW,
    )
    requirement = ObservationCompletenessRequirement(
        completeness_requirement_id=uid(2251),
        tenant_id=uid(1),
        organization_id=uid(2),
        observation_scope=ObservationScope.AUDIT_TRAIL,
        required_event_types=(ObservationEventType.AUDIT_RECORD_CREATED,),
        required_categories=(ObservationCategory.AUDIT,),
        policy_revision=1,
        requirement_revision=1,
        classification=DataClassification.CONFIDENTIAL,
        created_at=NOW,
    )
    assert policy.policy_document_reference == "policy://redaction/1"
    assert requirement.observation_scope is ObservationScope.AUDIT_TRAIL
    with pytest.raises(ValidationError):
        ObservationRedactionPolicyReference(
            **{**policy.model_dump(), "policy_content": "forbidden"}
        )


def test_complete_incomplete_and_not_applicable_assessments() -> None:
    assessment()
    assessment(
        ObservationCompletenessStatus.INCOMPLETE,
        missing_categories=(ObservationCategory.AUDIT,),
    )
    assessment(
        ObservationCompletenessStatus.NOT_APPLICABLE,
        observed_event_ids=(),
        reason_codes=("not-applicable",),
    )
    with pytest.raises(ValidationError):
        assessment(
            ObservationCompletenessStatus.COMPLETE,
            missing_categories=(ObservationCategory.AUDIT,),
        )
    with pytest.raises(ValidationError):
        assessment(ObservationCompletenessStatus.INCOMPLETE)


def test_completeness_ids_are_unique_and_canonical() -> None:
    with pytest.raises(ValidationError):
        assessment(observed_event_ids=(uid(2000), uid(2000)))
    with pytest.raises(ValidationError):
        ObservationCompletenessAssessment(**{**assessment().model_dump(), "percentage": 100})


def signal(**updates):
    combination = ExecutionCombinationIdentity(
        combination_id=uid(2400),
        tenant_scope=uid(1),
        quarantine_scope=QuarantineScope.TENANT,
        model_id="model-1",
        policy_revision="policy-1",
        registry_revision=1,
        created_at=NOW,
    )
    values = dict(
        deployment_stop_signal_id=uid(2401),
        tenant_scope=uid(1),
        quarantine_scope=QuarantineScope.TENANT,
        execution_combination=combination,
        triggering_observation_event_ids=(uid(2000),),
        security_violation_event_ids=(),
        quarantine_decision_ids=(),
        signal_reason_codes=("governance",),
        signal_status=DeploymentStopSignalStatus.RECORDED,
        policy_revision="policy-1",
        classification=DataClassification.CONFIDENTIAL,
        created_at=NOW,
    )
    values.update(updates)
    return DeploymentStopSignal(**values)


def test_deployment_stop_signal_is_metadata_only_and_scope_exact() -> None:
    signal()
    with pytest.raises(ValidationError):
        signal(triggering_observation_event_ids=())
    with pytest.raises(ValidationError):
        signal(tenant_scope=uid(99))
    with pytest.raises(ValidationError):
        signal(signal_status=DeploymentStopSignalStatus.CLEARED_BY_SEPARATE_DECISION)
    signal(
        signal_status=DeploymentStopSignalStatus.CLEARED_BY_SEPARATE_DECISION,
        clearing_governance_decision_reference="governance://clear/1",
    )


def test_bundle_builds_immutably_and_preserves_caller_order() -> None:
    request = bundle_request(
        declarations=(declaration(),),
        assessments=(assessment(),),
        signals=(signal(),),
    )
    bundle = build_observability_bundle(request)
    assert bundle.observation_events == request.observation_events
    assert bundle.audit_metadata.event_count == 1
    with pytest.raises(ValidationError):
        bundle.classification = DataClassification.PUBLIC


def test_bundle_rejects_duplicates_order_and_unknown_links() -> None:
    first = event()
    duplicate = event(occurred_at=NOW + timedelta(seconds=1))
    with pytest.raises(ValidationError):
        build_observability_bundle(bundle_request(events=(first, duplicate), audit=False))
    second = event(
        uid(2002),
        NOW + timedelta(seconds=1),
        correlation_context=context(uid(2002), parent_observation_id=uid(2000)),
        subject_reference=first.subject_reference.model_copy(
            update={"observation_subject_reference_id": uid(2011)}
        ),
        source_record_reference="audit://2002",
    )
    with pytest.raises(ValidationError):
        build_observability_bundle(bundle_request(events=(second, first), audit=False))
    with pytest.raises(ValidationError):
        build_observability_bundle(
            bundle_request(declarations=(declaration(uid(9999)),), audit=False)
        )


def test_bundle_rejects_cross_scope_completeness_signal_and_audit_mismatch() -> None:
    wrong_context = context(tenant_id=uid(99))
    wrong_subject = event().subject_reference.model_copy(update={"tenant_id": uid(99)})
    wrong_event = event(
        uid(2002),
        correlation_context=wrong_context,
        subject_reference=wrong_subject,
        source_record_reference="audit://2002",
    )
    with pytest.raises(ValidationError):
        build_observability_bundle(bundle_request(events=(event(), wrong_event), audit=False))
    wrong_assessment = assessment(correlation_id="other")
    with pytest.raises(ValidationError):
        build_observability_bundle(bundle_request(assessments=(wrong_assessment,), audit=False))
    with pytest.raises(ValidationError):
        build_observability_bundle(
            bundle_request(
                signals=(signal(triggering_observation_event_ids=(uid(9999),)),),
                audit=False,
            )
        )
    request = bundle_request()
    bad_audit = request.audit_metadata.model_copy(update={"event_count": 2})
    with pytest.raises(ValidationError):
        build_observability_bundle(request.model_copy(update={"audit_metadata": bad_audit}))


def test_parent_unknown_and_local_cycle_are_rejected() -> None:
    root = event()
    child_context = context(uid(2002), parent_observation_id=uid(9999))
    child = event(
        uid(2002),
        NOW + timedelta(seconds=1),
        correlation_context=child_context,
        subject_reference=root.subject_reference,
        source_record_reference="audit://2002",
    )
    with pytest.raises(ValidationError):
        build_observability_bundle(bundle_request(events=(root, child), audit=False))


def test_evaluation_pipeline_source_binding_is_exact() -> None:
    pipeline = pipeline_values()
    record = build_evaluation_pipeline_record(pipeline)
    correlation = context(
        tenant_id=record.tenant_id,
        organization_id=record.organization_id,
        evaluation_plan_id=record.evaluation_plan_id,
        evaluation_execution_id=record.evaluation_execution_id,
        evaluation_pipeline_id=record.pipeline_id,
    )
    subject = ObservationSubjectReference(
        observation_subject_reference_id=uid(2500),
        subject_type=ObservationSubjectType.EVALUATION_PIPELINE,
        subject_id=str(record.pipeline_id),
        subject_schema_version="pipeline-schema-v1",
        tenant_id=record.tenant_id,
        organization_id=record.organization_id,
        classification=DataClassification.CONFIDENTIAL,
        created_at=NOW,
    )
    observed = event(
        correlation_context=correlation,
        subject_reference=subject,
        category=ObservationCategory.EVALUATION,
        event_type=ObservationEventType.EVALUATION_PIPELINE_RECORDED,
        source_record_reference=f"evaluation-pipeline://{record.pipeline_id}",
    )
    validate_evaluation_pipeline_observation(observed, record)
    with pytest.raises(ObservabilityBindingMismatchError):
        validate_evaluation_pipeline_observation(
            observed.model_copy(update={"source_record_reference": "wrong"}), record
        )


def test_incomplete_audit_assessment_does_not_create_security_action() -> None:
    incomplete = assessment(
        ObservationCompletenessStatus.INCOMPLETE,
        missing_event_types=(ObservationEventType.AUDIT_RECORD_CREATED,),
    )
    audit_event = event(
        category=ObservationCategory.AUDIT,
        event_type=ObservationEventType.AUDIT_COMPLETENESS_FAILED,
        outcome=ObservationOutcome.FAILED,
    )
    validate_audit_quarantine_linkage(incomplete, audit_event)
    assert not hasattr(incomplete, "security_violation")
    assert not hasattr(audit_event, "quarantine_decision")


def test_security_and_quarantine_source_bindings_are_separate_and_exact() -> None:
    combination = signal().execution_combination
    violation = SecurityViolationEvent(
        violation_event_id=uid(2600),
        tenant_id=uid(1),
        organization_id=uid(2),
        agent_instance_id=uid(5),
        task_id=uid(6),
        combination_identity=combination,
        trigger_type=QuarantineTriggerType.AUDIT_LOG_MISSING,
        severity=SecurityViolationSeverity.CRITICAL,
        confirmed=True,
        resource_id="resource-1",
        action="observe",
        purpose="governance",
        risk_level="low",
        classification=DataClassification.CONFIDENTIAL,
        detected_at=NOW,
    )
    violation_subject = event().subject_reference.model_copy(
        update={
            "subject_type": ObservationSubjectType.SECURITY_VIOLATION,
            "subject_id": str(violation.violation_event_id),
        }
    )
    violation_event = event(
        subject_reference=violation_subject,
        category=ObservationCategory.ZERO_TRUST,
        event_type=ObservationEventType.SECURITY_VIOLATION_CONFIRMED,
        severity=ObservationSeverity.CRITICAL,
        source_record_reference=f"security-violation://{violation.violation_event_id}",
    )
    validate_security_violation_observation(violation_event, violation)
    decision = QuarantineDecision(
        quarantine_decision_id=uid(2601),
        violation_event_id=violation.violation_event_id,
        combination_identity=combination,
        tenant_scope=uid(1),
        outcome=QuarantineDecisionOutcome.QUARANTINE,
        policy_revision="policy-1",
        registry_revision=1,
        reason_codes=("audit-log-missing",),
        decided_at=NOW,
    )
    decision_subject = violation_subject.model_copy(
        update={
            "subject_type": ObservationSubjectType.QUARANTINE_DECISION,
            "subject_id": str(decision.quarantine_decision_id),
        }
    )
    decision_event = event(
        subject_reference=decision_subject,
        category=ObservationCategory.QUARANTINE,
        event_type=ObservationEventType.QUARANTINE_APPLIED,
        outcome=ObservationOutcome.QUARANTINED,
        source_record_reference=f"quarantine-decision://{decision.quarantine_decision_id}",
    )
    validate_quarantine_decision_observation(decision_event, decision)
    with pytest.raises(ObservabilityBindingMismatchError):
        validate_quarantine_decision_observation(violation_event, decision)
