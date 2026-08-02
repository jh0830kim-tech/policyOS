"""Focused network-free tests for immutable Runtime Authority contracts."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.runtime.authority import (
    OrphanRuntimeAuthorityReferenceError,
    RuntimeAdmissionDecision,
    RuntimeApprovalReference,
    RuntimeApprovalStatus,
    RuntimeAuthorityAuditMetadata,
    RuntimeAuthorityBundle,
    RuntimeAuthorityClassificationError,
    RuntimeAuthorityContext,
    RuntimeAuthorityContextError,
    RuntimeAuthorityContractVersion,
    RuntimeAuthorityDecisionStatus,
    RuntimeAuthorityTenantError,
    RuntimeAuthorizationReference,
    RuntimeAuthorizationStatus,
    RuntimeDenialReasonCode,
    RuntimeExecutionEnvironment,
    RuntimeExecutionRequest,
    RuntimeExecutionSubject,
    RuntimeExecutionSubjectType,
    RuntimePermitReference,
    RuntimePermitSourceType,
    RuntimePermitStatus,
    RuntimeReviewReference,
    RuntimeReviewStatus,
    RuntimeRiskLevel,
    build_runtime_authority_bundle,
    validate_runtime_authority_bundle,
    validate_runtime_authority_context,
    validate_runtime_execution_request,
    validate_runtime_permit_reference,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 8, 2, 12, tzinfo=UTC)


def uid(value: int) -> UUID:
    return UUID(int=value)


def version() -> RuntimeAuthorityContractVersion:
    return RuntimeAuthorityContractVersion(
        runtime_authority_version="authority-v1",
        runtime_authority_contract_version="contract-v1",
        runtime_authority_schema_version="schema-v1",
    )


def subject(**updates) -> RuntimeExecutionSubject:
    values = dict(
        runtime_execution_subject_id=uid(1),
        subject_type=RuntimeExecutionSubjectType.DECISION_PIPELINE,
        subject_id="decision-pipeline-1",
        subject_version="pipeline-v1",
        tenant_id=uid(2),
        organization_id=uid(3),
        classification=DataClassification.CONFIDENTIAL,
        root_lineage_id=uid(4),
        root_lineage_digest_reference="lineage-digest-1",
        created_at=NOW,
    )
    values.update(updates)
    return RuntimeExecutionSubject(**values)


def request(**updates) -> RuntimeExecutionRequest:
    values = dict(
        runtime_execution_request_id=uid(5),
        contract_version=version(),
        execution_subject=subject(),
        requester_actor_id=uid(6),
        requester_agent_instance_id=uid(7),
        on_behalf_of_user_id=uid(8),
        tenant_id=uid(2),
        organization_id=uid(3),
        resource_reference="resource-1",
        action="publish-policy",
        purpose="approved-policy-publication",
        risk_level=RuntimeRiskLevel.HIGH,
        classification=DataClassification.CONFIDENTIAL,
        execution_environment=RuntimeExecutionEnvironment.INTERNAL,
        model_id="model-1",
        provider_id="provider-1",
        tool_id="tool-1",
        connector_id="connector-1",
        destination_reference="destination-1",
        requested_invocation_count=1,
        requested_attempt_count=1,
        policy_revision=7,
        authorization_revision=8,
        registry_revision=9,
        lineage_id=uid(4),
        lineage_digest_reference="lineage-digest-1",
        requested_at=NOW + timedelta(minutes=1),
    )
    values.update(updates)
    return RuntimeExecutionRequest(**values)


def context(item: RuntimeExecutionRequest | None = None, **updates) -> RuntimeAuthorityContext:
    item = item or request()
    values = dict(
        runtime_authority_context_id=uid(9),
        runtime_execution_request_id=item.runtime_execution_request_id,
        tenant_id=item.tenant_id,
        organization_id=item.organization_id,
        actor_id=item.requester_actor_id,
        agent_instance_id=item.requester_agent_instance_id,
        on_behalf_of_user_id=item.on_behalf_of_user_id,
        resource_reference=item.resource_reference,
        action=item.action,
        purpose=item.purpose,
        risk_level=item.risk_level,
        classification=item.classification,
        execution_environment=item.execution_environment,
        model_id=item.model_id,
        provider_id=item.provider_id,
        tool_id=item.tool_id,
        connector_id=item.connector_id,
        destination_reference=item.destination_reference,
        policy_revision=item.policy_revision,
        authorization_revision=item.authorization_revision,
        registry_revision=item.registry_revision,
        context_lineage_id=item.lineage_id,
        context_lineage_digest_reference=item.lineage_digest_reference,
        created_at=item.requested_at + timedelta(minutes=1),
    )
    values.update(updates)
    return RuntimeAuthorityContext(**values)


def permit(item: RuntimeExecutionRequest | None = None, **updates) -> RuntimePermitReference:
    item = item or request()
    values = dict(
        runtime_permit_reference_id=uid(10),
        runtime_execution_request_id=item.runtime_execution_request_id,
        permit_source_type=RuntimePermitSourceType.ZERO_TRUST,
        external_permit_id="zero-trust-permit-1",
        permit_status=RuntimePermitStatus.ACTIVE,
        tenant_id=item.tenant_id,
        organization_id=item.organization_id,
        actor_id=item.requester_actor_id,
        agent_instance_id=item.requester_agent_instance_id,
        resource_reference=item.resource_reference,
        action=item.action,
        purpose=item.purpose,
        risk_level=item.risk_level,
        classification_ceiling=DataClassification.RESTRICTED,
        execution_environment=item.execution_environment,
        model_id=item.model_id,
        provider_id=item.provider_id,
        tool_id=item.tool_id,
        connector_id=item.connector_id,
        destination_reference=item.destination_reference,
        valid_from=item.requested_at + timedelta(minutes=2),
        expires_at=item.requested_at + timedelta(hours=1),
        maximum_invocations=1,
        remaining_invocations=1,
        maximum_attempts=1,
        remaining_attempts=1,
        policy_revision=item.policy_revision,
        authorization_revision=item.authorization_revision,
        registry_revision=item.registry_revision,
        permit_lineage_id=item.lineage_id,
        permit_lineage_digest_reference=item.lineage_digest_reference,
        created_at=item.requested_at + timedelta(minutes=1),
    )
    values.update(updates)
    return RuntimePermitReference(**values)


def admission(
    item: RuntimeExecutionRequest | None = None,
    authority_context: RuntimeAuthorityContext | None = None,
    **updates,
) -> RuntimeAdmissionDecision:
    item = item or request()
    authority_context = authority_context or context(item)
    values = dict(
        runtime_admission_decision_id=uid(11),
        contract_version=item.contract_version,
        runtime_execution_request_id=item.runtime_execution_request_id,
        runtime_authority_context_id=authority_context.runtime_authority_context_id,
        decision_status=RuntimeAuthorityDecisionStatus.ADMITTED,
        permit_reference_ids=(uid(10),),
        denial_reason_codes=(),
        decision_reference="admission-decision-1",
        actor_id=item.requester_actor_id,
        agent_instance_id=item.requester_agent_instance_id,
        tenant_id=item.tenant_id,
        organization_id=item.organization_id,
        classification=DataClassification.RESTRICTED,
        policy_revision=item.policy_revision,
        authorization_revision=item.authorization_revision,
        registry_revision=item.registry_revision,
        root_lineage_id=item.lineage_id,
        root_lineage_digest_reference=item.lineage_digest_reference,
        decided_at=item.requested_at + timedelta(minutes=3),
    )
    values.update(updates)
    return RuntimeAdmissionDecision(**values)


def bundle(**updates) -> RuntimeAuthorityBundle:
    item = request()
    authority_context = context(item)
    item_permit = permit(item)
    decision = admission(item, authority_context)
    bundle_id = uid(12)
    created = item.requested_at + timedelta(minutes=4)
    audit = RuntimeAuthorityAuditMetadata(
        runtime_authority_bundle_id=bundle_id,
        contract_version=item.contract_version,
        review_reference_count=0,
        approval_reference_count=0,
        authorization_reference_count=0,
        permit_reference_count=1,
        active_permit_count=1,
        revoked_permit_count=0,
        expired_permit_count=0,
        denial_reason_count=0,
        revocation_reference_count=0,
        tenant_id=item.tenant_id,
        organization_id=item.organization_id,
        classification=DataClassification.RESTRICTED,
        policy_revision=item.policy_revision,
        registry_revision=item.registry_revision,
        created_at=created,
    )
    values = dict(
        runtime_authority_bundle_id=bundle_id,
        contract_version=item.contract_version,
        execution_request=item,
        authority_context=authority_context,
        permit_references=(item_permit,),
        admission_decision=decision,
        tenant_id=item.tenant_id,
        organization_id=item.organization_id,
        classification=DataClassification.RESTRICTED,
        policy_revision=item.policy_revision,
        authorization_revision=item.authorization_revision,
        registry_revision=item.registry_revision,
        root_lineage_id=item.lineage_id,
        root_lineage_digest_reference=item.lineage_digest_reference,
        audit_metadata=audit,
        created_at=created,
    )
    values.update(updates)
    return RuntimeAuthorityBundle(**values)


def test_strict_frozen_extra_forbidden_and_caller_values_retained() -> None:
    item = request()
    assert validate_runtime_execution_request(item) is item
    with pytest.raises(ValidationError):
        RuntimeExecutionRequest(**{**item.model_dump(), "unexpected": "value"})
    with pytest.raises(ValidationError):
        item.action = "changed"
    with pytest.raises(ValidationError):
        request(requested_invocation_count=True)


def test_subject_request_scope_and_classification_fail_closed() -> None:
    item = request()
    assert item.execution_subject.subject_type is RuntimeExecutionSubjectType.DECISION_PIPELINE
    with pytest.raises(RuntimeAuthorityTenantError):
        validate_runtime_execution_request(request(tenant_id=uid(99)))
    with pytest.raises(RuntimeAuthorityClassificationError):
        validate_runtime_execution_request(request(classification=DataClassification.INTERNAL))


def test_request_preserves_all_bounded_selectors_without_payload_fields() -> None:
    item = request()
    assert (
        item.requester_actor_id,
        item.requester_agent_instance_id,
        item.resource_reference,
        item.action,
        item.purpose,
        item.risk_level,
        item.execution_environment,
        item.destination_reference,
        item.model_id,
        item.provider_id,
        item.tool_id,
        item.connector_id,
    ) == (
        uid(6),
        uid(7),
        "resource-1",
        "publish-policy",
        "approved-policy-publication",
        RuntimeRiskLevel.HIGH,
        RuntimeExecutionEnvironment.INTERNAL,
        "destination-1",
        "model-1",
        "provider-1",
        "tool-1",
        "connector-1",
    )
    assert not {"payload", "prompt", "output", "credential", "token", "secret"} & set(
        RuntimeExecutionRequest.model_fields
    )


def test_authority_context_requires_exact_request_scope() -> None:
    item = request()
    assert validate_runtime_authority_context(context(item), item)
    with pytest.raises(RuntimeAuthorityContextError):
        validate_runtime_authority_context(context(item, action="broader-action"), item)


@pytest.mark.parametrize(
    ("status", "extra"),
    (
        (RuntimeReviewStatus.REQUIRED, {}),
        (RuntimeReviewStatus.REQUESTED, {"external_review_request_reference": "review-request"}),
        (RuntimeReviewStatus.COMPLETED, {"external_review_result_reference": "review-result"}),
        (RuntimeReviewStatus.WAIVED, {"waiver_reference": "waiver"}),
        (RuntimeReviewStatus.CANCELLED, {"external_review_request_reference": "review-request"}),
    ),
)
def test_review_lifecycle_is_metadata_not_approval(status, extra) -> None:
    item = request()
    review = RuntimeReviewReference(
        runtime_review_reference_id=uid(20),
        runtime_execution_request_id=item.runtime_execution_request_id,
        review_type="security-review",
        review_status=status,
        tenant_id=item.tenant_id,
        organization_id=item.organization_id,
        classification=item.classification,
        policy_revision=item.policy_revision,
        created_at=item.requested_at,
        **extra,
    )
    assert review.review_status is status
    assert "approval_status" not in RuntimeReviewReference.model_fields


@pytest.mark.parametrize("status", tuple(RuntimeApprovalStatus))
def test_approval_lifecycle_remains_distinct(status) -> None:
    item = request()
    extra = {}
    if status in {RuntimeApprovalStatus.GRANTED, RuntimeApprovalStatus.DENIED}:
        extra["external_approval_decision_reference"] = "approval-decision"
    if status is RuntimeApprovalStatus.GRANTED:
        extra["valid_from"] = item.requested_at
    if status is RuntimeApprovalStatus.REVOKED:
        extra["revocation_reference"] = "approval-revocation"
    if status is RuntimeApprovalStatus.EXPIRED:
        extra["expires_at"] = item.requested_at + timedelta(minutes=1)
    approval = RuntimeApprovalReference(
        runtime_approval_reference_id=uid(21),
        runtime_execution_request_id=item.runtime_execution_request_id,
        approval_type="human-approval",
        approval_status=status,
        tenant_id=item.tenant_id,
        organization_id=item.organization_id,
        classification=item.classification,
        policy_revision=item.policy_revision,
        created_at=item.requested_at,
        **extra,
    )
    assert approval.approval_status is status
    assert "authorization_status" not in RuntimeApprovalReference.model_fields
    assert "permit_status" not in RuntimeApprovalReference.model_fields


@pytest.mark.parametrize("status", tuple(RuntimeAuthorizationStatus))
def test_authorization_lifecycle_retains_decisions_without_permit(status) -> None:
    item = request()
    extra = {}
    if status in {RuntimeAuthorizationStatus.GRANTED, RuntimeAuthorizationStatus.DENIED}:
        extra["external_authorization_decision_reference"] = "authorization-decision"
    if status is RuntimeAuthorizationStatus.GRANTED:
        extra["valid_from"] = item.requested_at
    if status is RuntimeAuthorizationStatus.REVOKED:
        extra["revocation_reference"] = "authorization-revocation"
    if status is RuntimeAuthorizationStatus.EXPIRED:
        extra["expires_at"] = item.requested_at + timedelta(minutes=1)
    authorization = RuntimeAuthorizationReference(
        runtime_authorization_reference_id=uid(22),
        runtime_execution_request_id=item.runtime_execution_request_id,
        authorization_type="policy-authorization",
        authorization_status=status,
        tenant_id=item.tenant_id,
        organization_id=item.organization_id,
        classification=item.classification,
        policy_revision=item.policy_revision,
        authorization_revision=item.authorization_revision,
        created_at=item.requested_at,
        **extra,
    )
    assert authorization.authorization_status is status
    assert "permit_status" not in RuntimeAuthorizationReference.model_fields


@pytest.mark.parametrize(
    "source", (RuntimePermitSourceType.ZERO_TRUST, RuntimePermitSourceType.MCP_GOVERNANCE)
)
def test_permit_sources_and_exact_scope_are_retained(source) -> None:
    item = request()
    item_permit = permit(item, permit_source_type=source)
    assert validate_runtime_permit_reference(item_permit, item) is item_permit
    assert not {"credential", "token", "secret", "bearer_token"} & set(
        RuntimePermitReference.model_fields
    )


def test_permit_bounds_and_classification_fail_closed() -> None:
    item = request()
    with pytest.raises(ValidationError):
        permit(item, remaining_invocations=2)
    with pytest.raises(ValidationError):
        permit(item, maximum_attempts=True)
    with pytest.raises(RuntimeAuthorityClassificationError):
        validate_runtime_permit_reference(
            permit(item, classification_ceiling=DataClassification.INTERNAL), item
        )


def test_admission_lifecycles_create_no_execution() -> None:
    denied = admission(
        decision_status=RuntimeAuthorityDecisionStatus.DENIED,
        permit_reference_ids=(),
        denial_reason_codes=(RuntimeDenialReasonCode.PERMIT_REQUIRED,),
    )
    not_applicable = admission(
        decision_status=RuntimeAuthorityDecisionStatus.NOT_APPLICABLE,
        permit_reference_ids=(),
    )
    invalidated = admission(
        decision_status=RuntimeAuthorityDecisionStatus.INVALIDATED,
        permit_reference_ids=(),
        original_admission_decision_id=uid(50),
        invalidation_reference="invalidation-1",
    )
    assert {denied.decision_status, not_applicable.decision_status, invalidated.decision_status}
    assert not {"execution_status", "result", "dispatch"} & set(
        RuntimeAdmissionDecision.model_fields
    )


def test_bundle_is_exact_immutable_and_audit_counts_match() -> None:
    item = bundle()
    assert validate_runtime_authority_bundle(item) is item
    assert build_runtime_authority_bundle(item) is item
    assert item.audit_metadata is not None
    assert item.audit_metadata.active_permit_count == 1


def test_bundle_rejects_orphan_admission_reference() -> None:
    item = bundle()
    bad = item.model_copy(
        update={
            "admission_decision": item.admission_decision.model_copy(
                update={"permit_reference_ids": (uid(99),)}
            )
        }
    )
    with pytest.raises(OrphanRuntimeAuthorityReferenceError):
        validate_runtime_authority_bundle(bad)


def test_production_boundary_has_no_runtime_or_issuance_implementation() -> None:
    root = ROOT / "app" / "runtime"
    sources = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    forbidden = (
        "datetime.now",
        "datetime.utcnow",
        "time.time",
        "uuid4",
        "random.",
        "hashlib",
        "subprocess",
        "httpx",
        "requests",
        "socket",
        "os.environ",
        "FastAPI",
        "sqlalchemy",
        "Redis",
        "issue_runtime_permit",
        "issue_runtime_approval",
        "issue_runtime_authorization",
    )
    assert all(term not in sources for term in forbidden)
    assert not any(
        (root / name).exists()
        for name in (
            "orchestration",
            "adapters",
            "persistence",
            "api",
            "workers",
            "scheduler",
            "repository",
            "routes",
            "services",
        )
    )
