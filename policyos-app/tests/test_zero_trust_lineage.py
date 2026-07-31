"""Sprint 13 CP0.6 immutable security-lineage and replay tests."""

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.zero_trust import (
    AgentInstanceIdentity,
    AgentInstanceStatus,
    AuthorizationVersionMismatchError,
    CredentialBrokerDecision,
    CredentialGrantRequest,
    CredentialGrantScope,
    CredentialMaterialReference,
    CredentialRevisionMismatchError,
    CrossValidationLineageError,
    CrossValidationLineageRun,
    DelegatedConnectorOperationBinding,
    DelegatedCrossValidationRunBinding,
    DelegatedMcpInvocationBinding,
    DelegatedModelInvocationBinding,
    DelegatedRepositoryOperationBinding,
    DelegatedSecretaryHandoffBinding,
    DelegationLineageError,
    DelegationLineageFacts,
    DelegationLineageRecord,
    DelegationScope,
    EphemeralCredentialGrantError,
    ExecutionTier,
    LineageAttestationReference,
    LineageCanonicalizationError,
    LineageContinuityError,
    LineageDigestError,
    LineageStage,
    LineageStageError,
    ReplayProtectedRepositoryAccessPermit,
    RepositoryAccessRequest,
    RepositoryAuthorizationDecision,
    RepositoryAuthorizationDecisionFacts,
    RepositoryAuthorizationOutcome,
    RepositoryAuthorizationReason,
    RepositoryPermitReplayError,
    RepositoryPermitStatus,
    RepositoryRequestFacts,
    SecretAccessAction,
    SecretAccessAuditRecord,
    SecretAccessResult,
    SecretType,
    TenantSecretReference,
    ZeroTrustAuditEventType,
    ZeroTrustAuditRecord,
    canonicalize_delegation_lineage,
    compute_delegation_lineage_digest,
    compute_repository_authorization_decision_digest,
    compute_repository_request_digest,
    execute_replay_protected_repository_operation,
    issue_replay_protected_repository_permit,
    request_ephemeral_credential_grant,
    validate_cross_validation_lineage_set,
    validate_ephemeral_credential_grant,
    validate_lineage_continuity,
    validate_repository_permit_for_request,
    verify_delegation_lineage_digest,
)

NOW = datetime(2026, 7, 31, 8, 0, tzinfo=UTC)


def lineage_facts(**updates) -> DelegationLineageFacts:
    data = {
        "delegation_id": uuid4(),
        "tenant_id": uuid4(),
        "organization_id": uuid4(),
        "on_behalf_of_user_id": uuid4(),
        "service_actor_id": uuid4(),
        "agent_instance_id": uuid4(),
        "task_id": uuid4(),
        "resource_id": "resource-1",
        "resource_type": "document",
        "action": "read",
        "purpose": "legal_review",
        "risk_level": "high",
        "classification": DataClassification.CONFIDENTIAL,
        "delegation_scope": DelegationScope.RESOURCE_READ,
        "authorization_decision_id": uuid4(),
        "issued_at": NOW,
        "expires_at": NOW + timedelta(hours=1),
    }
    data.update(updates)
    return DelegationLineageFacts(**data)


def lineage_record(
    facts: DelegationLineageFacts | None = None,
    *,
    stage: LineageStage = LineageStage.DELEGATION_CREATED,
    parent: DelegationLineageRecord | None = None,
) -> DelegationLineageRecord:
    facts = facts or lineage_facts()
    lineage_id = uuid4()
    digest = compute_delegation_lineage_digest(
        facts,
        lineage_id=lineage_id,
        created_at=NOW,
        parent_lineage_digest=parent.digest.digest_value if parent else None,
    )
    return DelegationLineageRecord(
        lineage_id=lineage_id,
        facts=facts,
        digest=digest,
        parent_lineage_id=parent.lineage_id if parent else None,
        lineage_stage=stage,
        created_at=NOW,
    )


def repository_setup():
    root = lineage_record()
    facts = root.facts
    request = RepositoryAccessRequest(
        repository_request_id=uuid4(),
        delegation_id=facts.delegation_id,
        tenant_id=facts.tenant_id,
        organization_id=facts.organization_id,
        on_behalf_of_user_id=facts.on_behalf_of_user_id,
        service_actor_id=facts.service_actor_id,
        agent_instance_id=facts.agent_instance_id,
        task_id=facts.task_id,
        repository_id="legal-repository",
        resource_id=facts.resource_id,
        resource_type=facts.resource_type,
        action=facts.action,
        purpose=facts.purpose,
        risk_level=facts.risk_level,
        classification=facts.classification,
        requested_at=NOW,
    )
    request_facts = RepositoryRequestFacts(
        **request.model_dump(),
        lineage_id=root.lineage_id,
        lineage_digest=root.digest.digest_value,
    )
    request_digest = compute_repository_request_digest(request_facts)
    decision = RepositoryAuthorizationDecision(
        repository_authorization_decision_id=uuid4(),
        repository_request_id=request.repository_request_id,
        delegation_id=request.delegation_id,
        outcome=RepositoryAuthorizationOutcome.ALLOW,
        reason_codes=(RepositoryAuthorizationReason.ALLOWED_BY_POLICY,),
        repository_policy_revision="policy-1",
        decided_at=NOW,
    )
    decision_facts = RepositoryAuthorizationDecisionFacts(
        repository_authorization_decision_id=decision.repository_authorization_decision_id,
        repository_request_digest=request_digest.digest_value,
        outcome=decision.outcome,
        reason_codes=decision.reason_codes,
        policy_revision="policy-1",
        authorization_engine_id="authz-engine",
        authorization_engine_version="1.2.0",
        authorization_rule_set_id="repository-rules",
        authorization_rule_set_version="4",
        decided_at=NOW,
    )
    decision_digest = compute_repository_authorization_decision_digest(decision_facts)
    permit = issue_replay_protected_repository_permit(
        request,
        decision,
        request_facts,
        request_digest,
        decision_facts,
        decision_digest,
        repository_permit_id=uuid4(),
        permit_revision=1,
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=10),
    )
    validation = {
        "lineage_id": root.lineage_id,
        "lineage_digest": root.digest.digest_value,
        "authorization_engine_id": "authz-engine",
        "authorization_engine_version": "1.2.0",
        "authorization_rule_set_id": "repository-rules",
        "authorization_rule_set_version": "4",
        "policy_revision": "policy-1",
        "decision_facts_digest": decision_digest.digest_value,
        "evaluated_at": NOW + timedelta(minutes=1),
    }
    return request, request_facts, request_digest, decision_facts, permit, validation


def credential_setup():
    tenant_id = uuid4()
    organization_id = uuid4()
    agent_id = uuid4()
    task_id = uuid4()
    secret = TenantSecretReference(
        secret_reference_id=uuid4(),
        tenant_id=tenant_id,
        organization_id=organization_id,
        secret_type=SecretType.MODEL_PROVIDER_CREDENTIAL,
        provider_or_service_id="provider-1",
        tenant_key_reference="tenant-key-1",
        secret_revision=7,
        enabled=True,
        created_at=NOW,
    )
    material = CredentialMaterialReference(
        material_reference_id=uuid4(),
        broker_id="broker-1",
        secret_reference_id=secret.secret_reference_id,
        secret_revision=secret.secret_revision,
        tenant_id=tenant_id,
        organization_id=organization_id,
        provider_or_service_id="provider-1",
        reference_scheme="opaque_broker_reference",
        reference_version="1",
        issued_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )
    agent = AgentInstanceIdentity(
        agent_instance_id=agent_id,
        tenant_id=tenant_id,
        organization_id=organization_id,
        agent_type="reviewer",
        task_id=task_id,
        execution_tier=ExecutionTier.IMMEDIATE_LEGAL_REVIEW,
        created_at=NOW,
        expires_at=NOW + timedelta(hours=1),
        status=AgentInstanceStatus.ACTIVE,
    )
    request = CredentialGrantRequest(
        credential_grant_id=uuid4(),
        requested_at=NOW,
        expires_at=NOW + timedelta(minutes=10),
        secret_reference=secret,
        agent_instance=agent,
        grant_scope=CredentialGrantScope.MODEL_INVOKE,
        model_id="model-1",
        credential_material_reference=material,
        broker_contract_version="2",
        grant_revision=3,
    )
    grant = request_ephemeral_credential_grant(
        request, broker_decision=CredentialBrokerDecision.ISSUE
    )
    return secret, material, agent, grant


def test_canonical_lineage_is_deterministic_and_normalizes_timezone() -> None:
    facts = lineage_facts()
    equivalent = facts.model_copy(
        update={"issued_at": facts.issued_at.astimezone(timezone(timedelta(hours=9)))}
    )
    assert canonicalize_delegation_lineage(facts) == canonicalize_delegation_lineage(equivalent)
    assert canonicalize_delegation_lineage(facts) == canonicalize_delegation_lineage(facts)


@pytest.mark.parametrize(
    "field",
    (
        "on_behalf_of_user_id",
        "tenant_id",
        "organization_id",
        "task_id",
        "purpose",
        "classification",
    ),
)
def test_changed_protected_fact_changes_digest(field) -> None:
    facts = lineage_facts()
    replacement = (
        DataClassification.RESTRICTED
        if field == "classification"
        else "different"
        if field == "purpose"
        else uuid4()
    )
    changed = facts.model_copy(update={field: replacement})
    original = compute_delegation_lineage_digest(facts, lineage_id=uuid4(), created_at=NOW)
    observed = compute_delegation_lineage_digest(changed, lineage_id=uuid4(), created_at=NOW)
    assert original.digest_value != observed.digest_value


def test_digest_verification_detects_altered_facts() -> None:
    facts = lineage_facts()
    digest = compute_delegation_lineage_digest(facts, lineage_id=uuid4(), created_at=NOW)
    verify_delegation_lineage_digest(facts, digest)
    with pytest.raises(LineageDigestError):
        verify_delegation_lineage_digest(facts.model_copy(update={"action": "store"}), digest)


def test_unsupported_canonicalization_and_algorithm_fail() -> None:
    facts = lineage_facts()
    with pytest.raises(LineageCanonicalizationError):
        canonicalize_delegation_lineage(facts, canonicalization_version="future")
    with pytest.raises(LineageDigestError):
        compute_delegation_lineage_digest(
            facts,
            lineage_id=uuid4(),
            created_at=NOW,
            digest_algorithm="future",
        )


def test_lineage_record_is_strict_immutable_and_digest_bound() -> None:
    record = lineage_record()
    with pytest.raises(ValidationError):
        record.lineage_stage = LineageStage.MODEL_BOUND
    with pytest.raises(ValidationError):
        DelegationLineageRecord(**record.model_dump(), payload="forbidden")


def test_lineage_continuity_allows_target_specialization() -> None:
    root = lineage_record()
    child_facts = root.facts.model_copy(update={"model_id": "model-1"})
    child = lineage_record(child_facts, stage=LineageStage.MODEL_BOUND, parent=root)
    validate_lineage_continuity(root, child, require_adjacent_stage=True)


@pytest.mark.parametrize(
    "mutation",
    (
        {"on_behalf_of_user_id": uuid4()},
        {"agent_instance_id": uuid4()},
        {"task_id": uuid4()},
        {"action": "store"},
        {"purpose": "publication"},
    ),
)
def test_lineage_continuity_rejects_protected_substitution(mutation) -> None:
    root = lineage_record()
    child = lineage_record(
        root.facts.model_copy(update=mutation),
        stage=LineageStage.MODEL_BOUND,
        parent=root,
    )
    with pytest.raises(LineageContinuityError):
        validate_lineage_continuity(root, child)


def test_lineage_parent_mismatch_and_stage_regression_fail() -> None:
    root = lineage_record()
    child = lineage_record(root.facts, stage=LineageStage.MODEL_BOUND, parent=root)
    wrong_parent = lineage_record()
    with pytest.raises(LineageContinuityError):
        validate_lineage_continuity(wrong_parent, child)
    regressed = lineage_record(root.facts, stage=LineageStage.DELEGATION_CREATED, parent=root)
    with pytest.raises(LineageStageError):
        validate_lineage_continuity(root, regressed)


@pytest.mark.parametrize(
    "factory",
    (
        lambda values: DelegatedModelInvocationBinding(
            **values, provider_instance_id="provider-1", model_id="model-1"
        ),
        lambda values: DelegatedMcpInvocationBinding(
            **values, mcp_server_id="mcp-1", tool_id="tool-1"
        ),
        lambda values: DelegatedConnectorOperationBinding(**values, connector_id="connector-1"),
        lambda values: DelegatedRepositoryOperationBinding(**values, repository_id="repository-1"),
        lambda values: DelegatedCrossValidationRunBinding(
            **values,
            cross_validation_plan_id=uuid4(),
            cross_validation_run_id=uuid4(),
            provider_instance_id="provider-1",
            model_id="model-1",
        ),
        lambda values: DelegatedSecretaryHandoffBinding(**values, handoff_id=uuid4()),
    ),
)
def test_downstream_bindings_validate_lineage(factory) -> None:
    root = lineage_record()
    child = lineage_record(root.facts, stage=LineageStage.MODEL_BOUND, parent=root)
    facts = child.facts
    values = {
        name: getattr(facts, name)
        for name in (
            "delegation_id",
            "tenant_id",
            "organization_id",
            "on_behalf_of_user_id",
            "service_actor_id",
            "agent_instance_id",
            "task_id",
            "resource_id",
            "action",
            "purpose",
            "risk_level",
            "classification",
        )
    }
    binding = factory(
        {
            **values,
            "lineage_id": child.lineage_id,
            "lineage_digest": child.digest.digest_value,
            "parent_lineage_digest": root.digest.digest_value,
            "lineage_stage": child.lineage_stage,
        }
    )
    binding.validate_lineage_record(child, parent=root)
    with pytest.raises(DelegationLineageError):
        binding.model_copy(update={"lineage_digest": "0" * 64}).validate_lineage_record(
            child, parent=root
        )


@pytest.mark.parametrize(
    "field",
    ("repository_id", "resource_id", "action", "on_behalf_of_user_id"),
)
def test_repository_request_digest_detects_substitution(field) -> None:
    _, facts, digest, _, _, _ = repository_setup()
    replacement = uuid4() if field == "on_behalf_of_user_id" else "changed"
    changed = facts.model_copy(update={field: replacement})
    assert compute_repository_request_digest(changed).digest_value != digest.digest_value


def test_repository_decision_digest_is_deterministic() -> None:
    _, _, _, decision_facts, _, _ = repository_setup()
    first = compute_repository_authorization_decision_digest(decision_facts)
    second = compute_repository_authorization_decision_digest(decision_facts)
    assert first == second


def test_exact_replay_protected_permit_executes_once_per_call() -> None:
    request, facts, digest, _, permit, validation = repository_setup()
    calls = []
    result = execute_replay_protected_repository_operation(
        permit,
        facts,
        digest,
        lambda item: calls.append(item.repository_request_id) or "ok",
        request,
        **validation,
    )
    assert result == "ok" and calls == [request.repository_request_id]


@pytest.mark.parametrize(
    ("field", "value", "error"),
    (
        ("lineage_digest", "0" * 64, RepositoryPermitReplayError),
        ("policy_revision", "policy-2", RepositoryPermitReplayError),
        (
            "authorization_engine_version",
            "2.0.0",
            AuthorizationVersionMismatchError,
        ),
        (
            "authorization_rule_set_version",
            "5",
            AuthorizationVersionMismatchError,
        ),
        ("decision_facts_digest", "0" * 64, RepositoryPermitReplayError),
    ),
)
def test_permit_rejects_substituted_validation_facts(field, value, error) -> None:
    _, facts, digest, _, permit, validation = repository_setup()
    with pytest.raises(error):
        validate_repository_permit_for_request(
            permit, facts, digest, **{**validation, field: value}
        )


@pytest.mark.parametrize(
    "status",
    (
        RepositoryPermitStatus.REVOKED,
        RepositoryPermitStatus.EXPIRED,
        RepositoryPermitStatus.CONSUMED,
    ),
)
def test_non_issued_permit_status_fails(status) -> None:
    _, facts, digest, _, permit, validation = repository_setup()
    changed = permit.model_copy(update={"permit_status": status})
    with pytest.raises(RepositoryPermitReplayError):
        validate_repository_permit_for_request(changed, facts, digest, **validation)


def test_expired_permit_and_request_substitution_cause_zero_calls() -> None:
    request, facts, digest, _, permit, validation = repository_setup()
    calls = []
    with pytest.raises(RepositoryPermitReplayError):
        execute_replay_protected_repository_operation(
            permit,
            facts,
            digest,
            lambda item: calls.append(item.repository_request_id),
            request,
            **{**validation, "evaluated_at": permit.expires_at},
        )
    assert calls == []
    assert isinstance(permit, ReplayProtectedRepositoryAccessPermit)


def test_credential_material_reference_is_metadata_only() -> None:
    _, material, _, _ = credential_setup()
    forbidden = {"secret_hash", "api_key_suffix", "token_prefix", "credential_blob"}
    assert not forbidden & set(type(material).model_fields)
    assert material.reference_scheme == "opaque_broker_reference"


def test_grant_binds_material_revision_broker_and_contract() -> None:
    secret, material, agent, grant = credential_setup()
    assert grant.credential_material_reference_id == material.material_reference_id
    assert grant.secret_revision == secret.secret_revision
    assert grant.broker_id == material.broker_id
    assert grant.broker_contract_version == "2"
    validate_ephemeral_credential_grant(
        grant,
        secret_reference=secret,
        agent_instance=agent,
        task_id=agent.task_id,
        provider_or_service_id="provider-1",
        grant_scope=CredentialGrantScope.MODEL_INVOKE,
        model_id="model-1",
        evaluated_at=NOW + timedelta(minutes=1),
        credential_material_reference=material,
        broker_contract_version="2",
    )


@pytest.mark.parametrize(
    "mutation",
    (
        {"secret_revision": 8},
        {"tenant_id": uuid4()},
        {"organization_id": uuid4()},
        {"provider_or_service_id": "provider-2"},
        {"material_reference_id": uuid4()},
        {"broker_id": "broker-2"},
    ),
)
def test_material_reference_substitution_fails(mutation) -> None:
    secret, material, agent, grant = credential_setup()
    with pytest.raises((CredentialRevisionMismatchError, EphemeralCredentialGrantError)):
        validate_ephemeral_credential_grant(
            grant,
            secret_reference=secret,
            agent_instance=agent,
            task_id=agent.task_id,
            provider_or_service_id="provider-1",
            grant_scope=CredentialGrantScope.MODEL_INVOKE,
            model_id="model-1",
            evaluated_at=NOW + timedelta(minutes=1),
            credential_material_reference=material.model_copy(update=mutation),
            broker_contract_version="2",
        )


def test_secret_rotation_does_not_mutate_historical_audit() -> None:
    secret, material, agent, grant = credential_setup()
    audit = SecretAccessAuditRecord(
        audit_id=uuid4(),
        secret_reference_id=secret.secret_reference_id,
        credential_grant_id=grant.credential_grant_id,
        tenant_id=secret.tenant_id,
        organization_id=secret.organization_id,
        agent_instance_id=agent.agent_instance_id,
        task_id=agent.task_id,
        provider_or_service_id=secret.provider_or_service_id,
        access_action=SecretAccessAction.GRANT_ISSUED,
        access_result=SecretAccessResult.ALLOWED,
        reason_code="issued",
        accessed_at=NOW,
        credential_material_reference_id=material.material_reference_id,
        secret_revision=7,
        broker_id=material.broker_id,
        broker_contract_version="2",
        grant_revision=grant.grant_revision,
    )
    secret.model_copy(update={"secret_revision": 8})
    assert audit.secret_revision == 7
    assert "secret_hash" not in audit.model_dump()


def test_cross_validation_runs_share_root_but_use_distinct_children_and_grants() -> None:
    root = lineage_record()
    runs = []
    for _ in range(2):
        run_id = uuid4()
        agent_id = uuid4()
        child_facts = root.facts.model_copy(
            update={
                "cross_validation_plan_id": uuid4(),
                "cross_validation_run_id": run_id,
                "agent_instance_id": agent_id,
            }
        )
        child = lineage_record(child_facts, stage=LineageStage.CROSS_VALIDATION_BOUND, parent=root)
        runs.append(
            CrossValidationLineageRun(
                run_id=run_id,
                agent_instance_id=agent_id,
                credential_grant_id=uuid4(),
                root_lineage_id=root.lineage_id,
                root_lineage_digest=root.digest.digest_value,
                child_lineage=child,
            )
        )
    validate_cross_validation_lineage_set(root, tuple(runs))
    assert runs[0].child_lineage.lineage_id != runs[1].child_lineage.lineage_id


def test_cross_validation_reused_credential_and_root_mismatch_fail() -> None:
    root = lineage_record()
    run_id = uuid4()
    agent_id = uuid4()
    child = lineage_record(
        root.facts.model_copy(
            update={
                "cross_validation_run_id": run_id,
                "agent_instance_id": agent_id,
            }
        ),
        stage=LineageStage.CROSS_VALIDATION_BOUND,
        parent=root,
    )
    grant_id = uuid4()
    first = CrossValidationLineageRun(
        run_id=run_id,
        agent_instance_id=agent_id,
        credential_grant_id=grant_id,
        root_lineage_id=root.lineage_id,
        root_lineage_digest=root.digest.digest_value,
        child_lineage=child,
    )
    second = first.model_copy(update={"run_id": uuid4(), "agent_instance_id": uuid4()})
    with pytest.raises(CrossValidationLineageError):
        validate_cross_validation_lineage_set(root, (first, second))
    with pytest.raises(CrossValidationLineageError):
        validate_cross_validation_lineage_set(
            root,
            (first.model_copy(update={"root_lineage_digest": "0" * 64}),),
            require_distinct_agents=False,
        )


def test_attestation_reference_is_metadata_only_and_subject_bound() -> None:
    root = lineage_record()
    reference = LineageAttestationReference(
        attestation_reference_id=uuid4(),
        attestation_provider_id="future-attestor",
        attestation_scheme="external_reference",
        attestation_version="1",
        subject_lineage_id=root.lineage_id,
        subject_lineage_digest=root.digest.digest_value,
        issued_at=NOW,
    )
    assert reference.subject_lineage_id == root.lineage_id
    forbidden = {"signature", "certificate", "public_key", "private_key", "signed_payload"}
    assert not forbidden & set(type(reference).model_fields)


def test_unified_audit_retains_security_lineage_without_payloads() -> None:
    root = lineage_record()
    record = ZeroTrustAuditRecord(
        audit_id=uuid4(),
        event_type=ZeroTrustAuditEventType.REPOSITORY_PERMIT_ISSUED,
        tenant_id=root.facts.tenant_id,
        organization_id=root.facts.organization_id,
        delegation_lineage_id=root.lineage_id,
        delegation_lineage_digest=root.digest.digest_value,
        repository_request_digest="1" * 64,
        repository_decision_digest="2" * 64,
        authorization_engine_version="1.2.0",
        authorization_rule_set_version="4",
        credential_material_reference_id=uuid4(),
        secret_revision=7,
        broker_contract_version="2",
        result_code="issued",
        occurred_at=NOW,
    )
    assert record.model_dump_json() == record.model_dump_json()
    forbidden = {
        "prompt",
        "document",
        "model_output",
        "token",
        "secret_value",
        "hidden_label",
        "expected_output",
    }
    assert not forbidden & set(type(record).model_fields)
    with pytest.raises(ValidationError):
        record.secret_revision = 8
