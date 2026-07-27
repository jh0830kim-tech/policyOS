from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.intelligence import CoordinationPurpose, WorkProductType
from app.orchestration import (
    SECRETARY_INTEGRATION_APPROVAL_PERMISSION,
    ApprovalAcknowledgementError,
    ApprovalActorError,
    ApprovalActorKind,
    ApprovalAuthorizationError,
    ApprovalAuthorizationEvidence,
    ApprovalDecision,
    ApprovalDuplicateError,
    ApprovalEligibilityError,
    ApprovalIdentityMismatchError,
    ApprovalSeparationOfDutiesError,
    ApprovalTimestampError,
    HumanApprovalDecisionInput,
    IntegrationConflictType,
    IntegrationGapType,
    IntegrationNextBoundary,
    SecretaryIntegrationApprovalContext,
    SecretaryIntegrationApprovalRequest,
    SecretaryIntegrationConflict,
    SecretaryIntegrationGap,
    SecretaryIntegrationResult,
    SecretaryIntegrationStatus,
    decide_secretary_integration_approval,
)

NOW = datetime(2026, 7, 27, tzinfo=UTC)
IDS = [UUID(f"{i:08d}-6666-6666-6666-666666666666") for i in range(1, 12)]
ORG = IDS[0]
INTEGRATION = IDS[1]
COORDINATION = IDS[2]
PRODUCTS = (IDS[3], IDS[4])
ALL_DECISIONS = tuple(sorted(ApprovalDecision, key=lambda item: item.value))


def conflict():
    return SecretaryIntegrationConflict(
        conflict_id="conflict.one",
        conflict_type=IntegrationConflictType.EXPLICIT_SOURCE_CONFLICT,
        source_work_product_ids=PRODUCTS,
        source_reference_ids=("evidence.one",),
        safe_description="Explicit source conflict.",
        blocking=True,
        requires_human_review=True,
    )


def gap():
    return SecretaryIntegrationGap(
        gap_id="gap.task.missing",
        gap_type=IntegrationGapType.MISSING_REQUIRED_PRODUCT,
        task_id="task.00.research",
        expected_work_product_type=WorkProductType.POLICY_ANALYSIS,
        blocking=True,
        safe_description="Required specialist product is missing.",
        next_boundary=IntegrationNextBoundary.REPLANNING,
    )


def integration(**changes):
    values = dict(
        integration_id=INTEGRATION,
        coordination_id=COORDINATION,
        purpose=CoordinationPurpose.INTEGRATED_POLICY_REPORT,
        organization_id=ORG,
        classification=DataClassification.RESTRICTED,
        status=SecretaryIntegrationStatus.READY,
        sections=(),
        source_work_product_ids=PRODUCTS,
        conflicts=(),
        gaps=(),
        missing_required_task_ids=(),
        omitted_optional_task_ids=(),
        human_review_task_ids=(),
        integrated_at=NOW,
    )
    values.update(changes)
    return SecretaryIntegrationResult(**values)


def request(**changes):
    values = dict(
        approval_request_id=IDS[5],
        integration_id=INTEGRATION,
        coordination_id=COORDINATION,
        organization_id=ORG,
        classification=DataClassification.RESTRICTED,
        requested_by_actor_id="office.secretary",
        requested_at=NOW + timedelta(minutes=1),
        source_integration_status=SecretaryIntegrationStatus.READY,
        source_integrated_at=NOW,
        source_work_product_ids=PRODUCTS,
    )
    values.update(changes)
    return SecretaryIntegrationApprovalRequest(**values)


def authorization(**changes):
    values = dict(
        actor_id="human.reviewer",
        actor_kind=ApprovalActorKind.HUMAN,
        organization_id=ORG,
        classification=DataClassification.RESTRICTED,
        permission_keys=(SECRETARY_INTEGRATION_APPROVAL_PERMISSION,),
    )
    values.update(changes)
    return ApprovalAuthorizationEvidence(**values)


def context(**changes):
    values = dict(
        approval_request_id=IDS[5],
        integration_id=INTEGRATION,
        coordination_id=COORDINATION,
        organization_id=ORG,
        classification=DataClassification.RESTRICTED,
        expected_requester_actor_id="office.secretary",
        secretary_actor_id="office.secretary",
        specialist_actor_ids=("office.policy_researcher", "office.statistics_analyst"),
        authorized_approver_actor_id="human.reviewer",
        authorization=authorization(),
        allowed_decisions=ALL_DECISIONS,
        approval_policy_id="approval-policy-v1",
        decided_at=NOW + timedelta(minutes=2),
    )
    values.update(changes)
    return SecretaryIntegrationApprovalContext(**values)


def decision(value=ApprovalDecision.APPROVED, **changes):
    values = dict(
        approval_record_id=IDS[6],
        approval_request_id=IDS[5],
        decision_id=IDS[7],
        integration_id=INTEGRATION,
        decision=value,
        approver_actor_id="human.reviewer",
        decided_at=NOW + timedelta(minutes=2),
        reason=None if value is ApprovalDecision.APPROVED else "Governance rationale.",
    )
    values.update(changes)
    return HumanApprovalDecisionInput(**values)


def decide(**changes):
    values = dict(
        request=request(),
        context=context(),
        decision=decision(),
        integration_result=integration(),
    )
    values.update(changes)
    return decide_secretary_integration_approval(**values)


def test_contracts_are_frozen_deterministic_bounded_and_explicit():
    first = request()
    assert first == first.model_copy()
    assert first.model_dump_json() == first.model_copy().model_dump_json()
    with pytest.raises(ValidationError):
        first.integration_id = IDS[0]
    with pytest.raises(ValidationError):
        decision(ApprovalDecision.REJECTED, reason=" ")
    with pytest.raises(ValidationError):
        decision(ApprovalDecision.REJECTED, reason="x" * 1001)


def test_ready_requires_explicit_authorized_human_approval():
    source = integration()
    record = decide(integration_result=source)
    assert record.decision is ApprovalDecision.APPROVED
    assert record.integration_id == source.integration_id
    assert record.approver_actor_id == "human.reviewer"
    assert source.status is SecretaryIntegrationStatus.READY


@pytest.mark.parametrize("status", [
    SecretaryIntegrationStatus.INCOMPLETE,
    SecretaryIntegrationStatus.NEEDS_REVIEW,
])
def test_non_ready_integration_cannot_be_approved(status):
    source = integration(status=status)
    with pytest.raises(ApprovalEligibilityError):
        decide(
            request=request(source_integration_status=status),
            integration_result=source,
        )


@pytest.mark.parametrize("source", [
    integration(conflicts=(conflict(),)),
    integration(gaps=(gap(),)),
    integration(human_review_task_ids=("task.00.research",)),
])
def test_ready_label_cannot_bypass_blockers_or_review(source):
    with pytest.raises(ApprovalEligibilityError):
        decide(integration_result=source)


@pytest.mark.parametrize("value", [
    ApprovalDecision.REJECTED,
    ApprovalDecision.CHANGES_REQUESTED,
])
def test_nonapproval_decisions_preserve_rationale_and_integration(value):
    source = integration(status=SecretaryIntegrationStatus.INCOMPLETE)
    record = decide(
        request=request(source_integration_status=SecretaryIntegrationStatus.INCOMPLETE),
        decision=decision(value),
        integration_result=source,
    )
    assert record.decision is value
    assert record.reason == "Governance rationale."
    assert source.status is SecretaryIntegrationStatus.INCOMPLETE


def test_machine_missing_permission_and_actor_impersonation_are_rejected():
    with pytest.raises(ApprovalActorError):
        decide(context=context(authorization=authorization(actor_kind=ApprovalActorKind.MACHINE)))
    with pytest.raises(ApprovalAuthorizationError):
        decide(context=context(authorization=authorization(permission_keys=())))
    with pytest.raises(ApprovalActorError):
        decide(decision=decision(approver_actor_id="human.other"))


@pytest.mark.parametrize("actor", [
    "office.secretary",
    "office.policy_researcher",
])
def test_separation_of_duties_rejects_secretary_and_producer(actor):
    with pytest.raises(ApprovalSeparationOfDutiesError):
        decide(
            context=context(
                authorized_approver_actor_id=actor,
                authorization=authorization(actor_id=actor),
            ),
            decision=decision(approver_actor_id=actor),
        )


def test_identity_and_timestamp_substitution_are_rejected():
    with pytest.raises(ApprovalIdentityMismatchError):
        decide(decision=decision(integration_id=IDS[0]))
    early = decision(decided_at=NOW)
    with pytest.raises(ApprovalTimestampError):
        decide(context=context(decided_at=NOW), decision=early)


def test_known_acknowledgements_are_preserved_and_unknown_rejected():
    source = integration(
        status=SecretaryIntegrationStatus.NEEDS_REVIEW,
        conflicts=(conflict(),),
        gaps=(gap(),),
        human_review_task_ids=("task.00.research",),
    )
    approved_decision = decision(
        ApprovalDecision.REJECTED,
        acknowledged_conflict_ids=("conflict.one",),
        acknowledged_gap_ids=("gap.task.missing",),
        acknowledged_review_task_ids=("task.00.research",),
    )
    record = decide(
        request=request(source_integration_status=SecretaryIntegrationStatus.NEEDS_REVIEW),
        decision=approved_decision,
        integration_result=source,
    )
    assert record.acknowledged_conflict_ids == ("conflict.one",)
    with pytest.raises(ApprovalAcknowledgementError):
        decide(
            request=request(source_integration_status=SecretaryIntegrationStatus.NEEDS_REVIEW),
            decision=decision(
                ApprovalDecision.REJECTED,
                acknowledged_conflict_ids=("conflict.unknown",),
            ),
            integration_result=source,
        )


def test_prior_record_makes_request_and_decision_identity_immutable():
    record = decide()
    with pytest.raises(ApprovalDuplicateError):
        decide(prior_records=(record,))


def test_no_provider_automatic_approval_or_later_scope():
    import inspect

    import app.orchestration.approval as module

    source = inspect.getsource(module).lower()
    for forbidden in (
        "provider_id", "model_id", "openai", "anthropic", "gemini",
        "datetime.now", "uuid4", "database", "retry(", "fallback(",
        "confidence", "publish", "notification", "cross_validation",
    ):
        assert forbidden not in source
