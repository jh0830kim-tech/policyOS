"""Sprint 13 CP0.5 zero-trust security contract tests."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.zero_trust import (
    MANDATORY_CRITICAL_TRIGGERS,
    AgentInstanceError,
    AgentInstanceIdentity,
    AgentInstanceStatus,
    CredentialBrokerDecision,
    CredentialGrantRequest,
    CredentialGrantScope,
    CredentialRevocationStatus,
    DelegatedConnectorOperationBinding,
    DelegatedCrossValidationRunBinding,
    DelegatedExecutionContext,
    DelegatedMcpInvocationBinding,
    DelegatedModelInvocationBinding,
    DelegatedRepositoryOperationBinding,
    DelegatedSecretaryHandoffBinding,
    DelegationLineageError,
    DelegationScope,
    DelegationValidationError,
    EphemeralCredentialGrantError,
    EvaluationDataAccessContext,
    EvaluationDataAccessOutcome,
    EvaluationDataPolicyFacts,
    EvaluationDataType,
    ExecutionCombinationIdentity,
    ExecutionTier,
    IsolationLevel,
    NetworkPolicy,
    QuarantineDecisionOutcome,
    QuarantineEnforcementError,
    QuarantineRegistryEntry,
    QuarantineRegistrySnapshot,
    QuarantineRegistryStatus,
    QuarantineReleaseError,
    QuarantineReleaseOutcome,
    QuarantineReleaseRequest,
    QuarantineScope,
    QuarantineTriggerType,
    RepositoryAccessRequest,
    RepositoryAuthorizationOutcome,
    RepositoryPermitError,
    RepositoryPolicyFacts,
    SecretAccessAction,
    SecretAccessAuditRecord,
    SecretAccessResult,
    SecretType,
    SecurityViolationEvent,
    SecurityViolationSeverity,
    TaskCompletionRecord,
    TaskExecutionPolicy,
    TenantExecutionBoundary,
    TenantIsolationError,
    TenantSecretReference,
    ZeroTrustAuditEventType,
    ZeroTrustAuditRecord,
    decide_quarantine_release,
    enforce_not_quarantined,
    evaluate_evaluation_data_access,
    evaluate_quarantine_policy,
    evaluate_repository_access_policy,
    execute_authorized_repository_operation,
    issue_repository_access_permit,
    request_ephemeral_credential_grant,
    require_termination_after_completion,
    revoke_ephemeral_credential_grant,
    validate_delegation_scope,
    validate_distinct_tenant_boundaries,
    validate_ephemeral_credential_grant,
    validate_retry_identity,
    validate_tenant_key_isolation,
)

NOW = datetime(2026, 7, 31, 7, 0, tzinfo=UTC)


def ids() -> dict[str, UUID]:
    return {
        name: uuid4()
        for name in (
            "tenant",
            "organization",
            "user",
            "service",
            "agent",
            "task",
            "delegation",
            "authorization",
            "plan",
            "run",
        )
    }


def delegation(**updates) -> DelegatedExecutionContext:
    value = ids()
    data = {
        "delegation_id": value["delegation"],
        "tenant_id": value["tenant"],
        "organization_id": value["organization"],
        "on_behalf_of_user_id": value["user"],
        "service_actor_id": value["service"],
        "agent_instance_id": value["agent"],
        "task_id": value["task"],
        "resource_id": "resource-1",
        "resource_type": "document",
        "action": "read",
        "purpose": "legal_review",
        "risk_level": "high",
        "classification": DataClassification.CONFIDENTIAL,
        "delegation_scope": DelegationScope.RESOURCE_READ,
        "authorization_decision_id": value["authorization"],
        "issued_at": NOW,
        "expires_at": NOW + timedelta(hours=1),
        "provider_instance_id": "provider-1",
        "model_id": "model-1",
        "mcp_server_id": "mcp-1",
        "tool_id": "tool-1",
        "connector_id": "connector-1",
        "cross_validation_plan_id": value["plan"],
        "cross_validation_run_id": value["run"],
    }
    data.update(updates)
    return DelegatedExecutionContext(**data)


def binding_data(context: DelegatedExecutionContext) -> dict:
    return {
        field: getattr(context, field)
        for field in (
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


def agent(context: DelegatedExecutionContext, **updates) -> AgentInstanceIdentity:
    data = {
        "agent_instance_id": context.agent_instance_id,
        "tenant_id": context.tenant_id,
        "organization_id": context.organization_id,
        "agent_type": "legal_reviewer",
        "task_id": context.task_id,
        "execution_tier": ExecutionTier.IMMEDIATE_LEGAL_REVIEW,
        "created_at": NOW,
        "expires_at": NOW + timedelta(hours=1),
        "status": AgentInstanceStatus.ACTIVE,
    }
    data.update(updates)
    return AgentInstanceIdentity(**data)


def secret(context: DelegatedExecutionContext, **updates) -> TenantSecretReference:
    data = {
        "secret_reference_id": uuid4(),
        "tenant_id": context.tenant_id,
        "organization_id": context.organization_id,
        "secret_type": SecretType.MODEL_PROVIDER_CREDENTIAL,
        "provider_or_service_id": "provider-1",
        "tenant_key_reference": f"tenant-key:{context.tenant_id}",
        "secret_revision": 1,
        "enabled": True,
        "created_at": NOW,
    }
    data.update(updates)
    return TenantSecretReference(**data)


def repository_request(context: DelegatedExecutionContext, **updates) -> RepositoryAccessRequest:
    data = {
        **binding_data(context),
        "repository_request_id": uuid4(),
        "repository_id": "legal-repository",
        "resource_type": context.resource_type,
        "requested_at": NOW + timedelta(minutes=1),
    }
    data.update(updates)
    return RepositoryAccessRequest(**data)


def repository_facts(context: DelegatedExecutionContext, **updates) -> RepositoryPolicyFacts:
    data = {
        "active_user": True,
        "membership_exists": True,
        "membership_active": True,
        "membership_tenant_id": context.tenant_id,
        "membership_organization_id": context.organization_id,
        "membership_user_id": context.on_behalf_of_user_id,
        "allowed_resource_ids": (context.resource_id,),
        "allowed_actions": (context.action,),
        "allowed_purposes": (context.purpose,),
        "allowed_risk_levels": (context.risk_level,),
        "allowed_classifications": (context.classification,),
        "delegation_valid": True,
        "expected_service_actor_id": context.service_actor_id,
        "expected_agent_instance_id": context.agent_instance_id,
        "repository_policy_revision": "repo-policy-1",
    }
    data.update(updates)
    return RepositoryPolicyFacts(**data)


def combination(context: DelegatedExecutionContext, **updates) -> ExecutionCombinationIdentity:
    data = {
        "combination_id": uuid4(),
        "tenant_scope": context.tenant_id,
        "quarantine_scope": QuarantineScope.TENANT,
        "provider_instance_id": "provider-1",
        "model_id": "model-1",
        "policy_revision": "security-policy-1",
        "registry_revision": 1,
        "created_at": NOW,
    }
    data.update(updates)
    return ExecutionCombinationIdentity(**data)


def test_delegation_requires_user_and_distinct_service_actor() -> None:
    with pytest.raises(ValidationError):
        delegation(on_behalf_of_user_id=None)
    shared_identity = uuid4()
    with pytest.raises((DelegationValidationError, ValidationError)):
        delegation(
            service_actor_id=shared_identity,
            on_behalf_of_user_id=shared_identity,
        )


def test_delegation_is_immutable_strict_and_expiry_fails_closed() -> None:
    context = delegation()
    with pytest.raises(ValidationError):
        context.task_id = uuid4()
    with pytest.raises(ValidationError):
        DelegatedExecutionContext(**context.model_dump(), administrator=True)
    with pytest.raises(DelegationValidationError):
        context.require_valid_at(context.expires_at)


@pytest.mark.parametrize(
    ("scope", "forbidden"),
    (
        (DelegationScope.LEGAL_SEARCH, DelegationScope.INTERNAL_RESULT_STORE),
        (DelegationScope.RESOURCE_SUMMARIZE, DelegationScope.EXTERNAL_TRANSMISSION),
        (DelegationScope.INTERNAL_RESULT_STORE, DelegationScope.PUBLICATION_REQUEST),
        (DelegationScope.MCP_TOOL_INVOKE, DelegationScope.CONNECTOR_READ),
    ),
)
def test_delegation_scopes_do_not_expand(scope, forbidden) -> None:
    context = delegation(delegation_scope=scope)
    with pytest.raises(DelegationValidationError):
        validate_delegation_scope(context, forbidden)


@pytest.mark.parametrize(
    "factory",
    (
        lambda c: DelegatedModelInvocationBinding(
            **binding_data(c),
            provider_instance_id=c.provider_instance_id,
            model_id=c.model_id,
        ),
        lambda c: DelegatedMcpInvocationBinding(
            **binding_data(c), mcp_server_id=c.mcp_server_id, tool_id=c.tool_id
        ),
        lambda c: DelegatedConnectorOperationBinding(
            **binding_data(c), connector_id=c.connector_id
        ),
        lambda c: DelegatedRepositoryOperationBinding(
            **binding_data(c), repository_id="legal-repository"
        ),
        lambda c: DelegatedCrossValidationRunBinding(
            **binding_data(c),
            cross_validation_plan_id=c.cross_validation_plan_id,
            cross_validation_run_id=c.cross_validation_run_id,
            provider_instance_id=c.provider_instance_id,
            model_id=c.model_id,
        ),
        lambda c: DelegatedSecretaryHandoffBinding(
            **binding_data(c),
            handoff_id=uuid4(),
            cross_validation_plan_id=c.cross_validation_plan_id,
            cross_validation_run_id=c.cross_validation_run_id,
        ),
    ),
)
def test_all_downstream_bindings_preserve_exact_user_lineage(factory) -> None:
    context = delegation()
    binding = factory(context)
    binding.validate_delegation(context)
    changed = context.model_copy(update={"on_behalf_of_user_id": uuid4()})
    with pytest.raises(DelegationLineageError):
        binding.validate_delegation(changed)


@pytest.mark.parametrize(
    ("fact_update", "reason"),
    (
        ({"active_user": False}, "user_inactive"),
        ({"membership_exists": False}, "membership_missing"),
        ({"membership_active": False}, "membership_inactive"),
        ({"membership_tenant_id": uuid4()}, "tenant_mismatch"),
        ({"membership_organization_id": uuid4()}, "organization_mismatch"),
        ({"membership_user_id": uuid4()}, "user_mismatch"),
        ({"allowed_resource_ids": ()}, "resource_denied"),
        ({"allowed_actions": ()}, "action_denied"),
        ({"allowed_classifications": ()}, "classification_denied"),
        ({"delegation_valid": False}, "delegation_invalid"),
    ),
)
def test_repository_independently_denies_policy_failures(fact_update, reason) -> None:
    context = delegation()
    request = repository_request(context)
    decision = evaluate_repository_access_policy(
        request,
        context,
        repository_facts(context, **fact_update),
        repository_authorization_decision_id=uuid4(),
        decided_at=NOW + timedelta(minutes=1),
    )
    assert decision.outcome is RepositoryAuthorizationOutcome.DENY
    assert reason in {item.value for item in decision.reason_codes}


def test_repository_denial_causes_zero_calls_and_exact_permit_one_call() -> None:
    context = delegation()
    request = repository_request(context)
    denied = evaluate_repository_access_policy(
        request,
        context,
        repository_facts(context, active_user=False),
        repository_authorization_decision_id=uuid4(),
        decided_at=NOW + timedelta(minutes=1),
    )
    calls: list[UUID] = []
    with pytest.raises(RepositoryPermitError):
        issue_repository_access_permit(
            request, denied, repository_permit_id=uuid4(), issued_at=NOW
        )
    assert calls == []
    allowed = evaluate_repository_access_policy(
        request,
        context,
        repository_facts(context),
        repository_authorization_decision_id=uuid4(),
        decided_at=NOW + timedelta(minutes=1),
    )
    permit = issue_repository_access_permit(
        request,
        allowed,
        repository_permit_id=uuid4(),
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    result = execute_authorized_repository_operation(
        request,
        permit,
        lambda item: calls.append(item.repository_request_id) or "result",
        repository_policy_revision="repo-policy-1",
        evaluated_at=NOW + timedelta(minutes=2),
    )
    assert result == "result"
    assert calls == [request.repository_request_id]
    with pytest.raises(RepositoryPermitError):
        execute_authorized_repository_operation(
            repository_request(context),
            permit,
            lambda item: calls.append(item.repository_request_id),
            repository_policy_revision="repo-policy-1",
            evaluated_at=NOW + timedelta(minutes=2),
        )
    assert len(calls) == 1


@pytest.mark.parametrize(
    "status",
    (
        AgentInstanceStatus.TERMINATED,
        AgentInstanceStatus.QUARANTINED,
        AgentInstanceStatus.EXPIRED,
    ),
)
def test_terminal_agent_cannot_receive_credentials(status) -> None:
    context = delegation()
    with pytest.raises(AgentInstanceError):
        agent(context, status=status).require_credential_eligible(NOW + timedelta(minutes=1))


def test_secret_reference_and_grant_are_metadata_only_and_exact() -> None:
    context = delegation()
    instance = agent(context)
    reference = secret(context)
    request = CredentialGrantRequest(
        credential_grant_id=uuid4(),
        requested_at=NOW + timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=5),
        secret_reference=reference,
        agent_instance=instance,
        grant_scope=CredentialGrantScope.MODEL_INVOKE,
        model_id="model-1",
    )
    grant = request_ephemeral_credential_grant(
        request, broker_decision=CredentialBrokerDecision.ISSUE
    )
    serialized = grant.model_dump_json()
    assert "Policy content" not in serialized and "token" not in serialized
    validate_ephemeral_credential_grant(
        grant,
        secret_reference=reference,
        agent_instance=instance,
        task_id=context.task_id,
        provider_or_service_id="provider-1",
        grant_scope=CredentialGrantScope.MODEL_INVOKE,
        model_id="model-1",
        evaluated_at=NOW + timedelta(minutes=2),
    )
    with pytest.raises(EphemeralCredentialGrantError):
        validate_ephemeral_credential_grant(
            grant,
            secret_reference=reference,
            agent_instance=agent(context, agent_instance_id=uuid4()),
            task_id=context.task_id,
            provider_or_service_id="provider-1",
            grant_scope=CredentialGrantScope.MODEL_INVOKE,
            model_id="model-1",
            evaluated_at=NOW + timedelta(minutes=2),
        )
    revoked = revoke_ephemeral_credential_grant(
        grant, revocation_status=CredentialRevocationStatus.REVOKED
    )
    assert revoked.revocation_status is CredentialRevocationStatus.REVOKED


def test_cross_tenant_secret_and_key_reuse_fail() -> None:
    first_context = delegation()
    second_context = delegation()
    first = secret(first_context, tenant_key_reference="shared-key")
    second = secret(second_context, tenant_key_reference="shared-key")
    with pytest.raises(TenantIsolationError):
        validate_tenant_key_isolation((first, second))
    with pytest.raises(TenantIsolationError):
        request_ephemeral_credential_grant(
            CredentialGrantRequest(
                credential_grant_id=uuid4(),
                requested_at=NOW,
                expires_at=NOW + timedelta(minutes=1),
                secret_reference=first,
                agent_instance=agent(second_context),
                grant_scope=CredentialGrantScope.MODEL_INVOKE,
                model_id="model-1",
            ),
            broker_decision=CredentialBrokerDecision.ISSUE,
        )


def test_secret_audit_has_metadata_only_strict_shape() -> None:
    context = delegation()
    record = SecretAccessAuditRecord(
        audit_id=uuid4(),
        secret_reference_id=uuid4(),
        credential_grant_id=uuid4(),
        tenant_id=context.tenant_id,
        organization_id=context.organization_id,
        agent_instance_id=context.agent_instance_id,
        task_id=context.task_id,
        provider_or_service_id="provider-1",
        access_action=SecretAccessAction.GRANT_ISSUED,
        access_result=SecretAccessResult.ALLOWED,
        reason_code="broker_approved",
        accessed_at=NOW,
    )
    assert "secret_value" not in record.model_dump()
    with pytest.raises(ValidationError):
        SecretAccessAuditRecord(**record.model_dump(), token="forbidden")


@pytest.mark.parametrize("trigger", tuple(sorted(MANDATORY_CRITICAL_TRIGGERS, key=str)))
def test_each_confirmed_mandatory_trigger_quarantines_on_first_event(trigger) -> None:
    context = delegation()
    target = combination(context)
    event = SecurityViolationEvent(
        violation_event_id=uuid4(),
        tenant_id=context.tenant_id,
        organization_id=context.organization_id,
        agent_instance_id=context.agent_instance_id,
        task_id=context.task_id,
        combination_identity=target,
        trigger_type=trigger,
        severity=SecurityViolationSeverity.CRITICAL,
        confirmed=True,
        resource_id=context.resource_id,
        action=context.action,
        purpose=context.purpose,
        risk_level=context.risk_level,
        classification=context.classification,
        detected_at=NOW,
    )
    decision = evaluate_quarantine_policy(
        event,
        quarantine_decision_id=uuid4(),
        policy_revision="security-policy-1",
        registry_revision=1,
        decided_at=NOW,
    )
    assert decision.outcome is QuarantineDecisionOutcome.QUARANTINE


def test_quarantine_blocks_exact_combination_not_unrelated_or_other_tenant() -> None:
    context = delegation()
    target = combination(context)
    entry = QuarantineRegistryEntry(
        combination_identity=target,
        status=QuarantineRegistryStatus.QUARANTINED,
        violation_event_ids=(uuid4(),),
        quarantine_decision_ids=(uuid4(),),
        updated_at=NOW,
    )
    snapshot = QuarantineRegistrySnapshot(
        registry_id=uuid4(),
        registry_revision=1,
        entries=(entry,),
        created_at=NOW,
    )
    with pytest.raises(QuarantineEnforcementError):
        enforce_not_quarantined(target.model_copy(update={"combination_id": uuid4()}), snapshot)
    enforce_not_quarantined(combination(context, model_id="unrelated-model"), snapshot)
    enforce_not_quarantined(
        combination(context, tenant_scope=uuid4(), combination_id=uuid4()), snapshot
    )


def test_global_quarantine_requires_explicit_scope() -> None:
    context = delegation()
    with pytest.raises(ValueError):
        combination(context, quarantine_scope=QuarantineScope.GLOBAL)
    global_target = combination(
        context, quarantine_scope=QuarantineScope.GLOBAL, tenant_scope=None
    )
    assert global_target.tenant_scope is None


def test_release_requires_separate_reviewer_evidence_and_new_revision() -> None:
    context = delegation()
    request = QuarantineReleaseRequest(
        release_request_id=uuid4(),
        combination_identity=combination(context),
        original_violation_event_ids=(uuid4(),),
        original_quarantine_decision_ids=(uuid4(),),
        requested_by_actor_id=uuid4(),
        quarantined_agent_instance_id=context.agent_instance_id,
        remediation_references=("remediation-1",),
        security_review_references=("review-1",),
        requested_at=NOW,
    )
    with pytest.raises((QuarantineReleaseError, ValidationError)):
        decide_quarantine_release(
            request,
            release_decision_id=uuid4(),
            reviewer_actor_id=context.agent_instance_id,
            outcome=QuarantineReleaseOutcome.APPROVE_RELEASE,
            reason_codes=("fixed",),
            prior_registry_revision=1,
            new_registry_revision=2,
            decided_at=NOW,
        )
    approved = decide_quarantine_release(
        request,
        release_decision_id=uuid4(),
        reviewer_actor_id=uuid4(),
        outcome=QuarantineReleaseOutcome.APPROVE_RELEASE,
        reason_codes=("fixed",),
        prior_registry_revision=1,
        new_registry_revision=2,
        decided_at=NOW,
    )
    assert approved.original_violation_event_ids == request.original_violation_event_ids


@pytest.mark.parametrize(
    "tier",
    (
        ExecutionTier.DEFERRED_BACKGROUND,
        ExecutionTier.SCHEDULED_BATCH,
        ExecutionTier.OFFLINE_EVALUATION,
    ),
)
def test_delay_tolerant_tiers_require_stop_after_completion(tier) -> None:
    context = delegation()
    with pytest.raises(ValueError):
        TaskExecutionPolicy(
            task_policy_id=uuid4(),
            tenant_id=context.tenant_id,
            organization_id=context.organization_id,
            task_type="daily_brief",
            execution_tier=tier,
            maximum_runtime_seconds=600,
            stop_after_completion=False,
            persistent_agent_allowed=True,
            network_policy=NetworkPolicy.INTERNAL_ONLY,
            isolation_level=IsolationLevel.TENANT_DEDICATED,
            created_at=NOW,
        )


def test_completion_requires_termination_and_retry_has_new_identity() -> None:
    context = delegation()
    grant_id = uuid4()
    completion = TaskCompletionRecord(
        completion_id=uuid4(),
        tenant_id=context.tenant_id,
        organization_id=context.organization_id,
        task_id=context.task_id,
        task_attempt_id=uuid4(),
        agent_instance_id=context.agent_instance_id,
        execution_tier=ExecutionTier.DEFERRED_BACKGROUND,
        completed_at=NOW,
        credential_grant_ids=(grant_id,),
    )
    policy = TaskExecutionPolicy(
        task_policy_id=uuid4(),
        tenant_id=context.tenant_id,
        organization_id=context.organization_id,
        task_type="daily_brief",
        execution_tier=ExecutionTier.DEFERRED_BACKGROUND,
        maximum_runtime_seconds=600,
        stop_after_completion=True,
        persistent_agent_allowed=False,
        network_policy=NetworkPolicy.INTERNAL_ONLY,
        isolation_level=IsolationLevel.TENANT_DEDICATED,
        created_at=NOW,
    )
    requirement = require_termination_after_completion(
        completion, policy, termination_requirement_id=uuid4(), required_at=NOW
    )
    assert requirement.required_status is AgentInstanceStatus.TERMINATED
    with pytest.raises(AgentInstanceError):
        validate_retry_identity(
            completion,
            new_task_attempt_id=completion.task_attempt_id,
            new_agent_instance_id=uuid4(),
            new_credential_grant_ids=(uuid4(),),
        )
    validate_retry_identity(
        completion,
        new_task_attempt_id=uuid4(),
        new_agent_instance_id=uuid4(),
        new_credential_grant_ids=(uuid4(),),
    )


def test_tenant_boundaries_cannot_share_worker_or_key() -> None:
    contexts = (delegation(), delegation())
    boundaries = tuple(
        TenantExecutionBoundary(
            execution_boundary_id=uuid4(),
            tenant_id=context.tenant_id,
            organization_id=context.organization_id,
            worker_pool_id="shared-pool",
            isolation_level=IsolationLevel.TENANT_DEDICATED,
            encryption_key_reference=f"key:{index}",
            network_policy=NetworkPolicy.INTERNAL_ONLY,
            allowed_execution_tiers=(ExecutionTier.IMMEDIATE_INTERACTIVE,),
            created_at=NOW,
        )
        for index, context in enumerate(contexts)
    )
    with pytest.raises(TenantIsolationError):
        validate_distinct_tenant_boundaries(boundaries)


@pytest.mark.parametrize(
    ("data_type", "production_agent", "evaluated_model"),
    (
        (EvaluationDataType.HIDDEN_LABEL, True, False),
        (EvaluationDataType.EXPECTED_OUTPUT, False, True),
    ),
)
def test_protected_evaluation_data_denial_triggers_quarantine(
    data_type, production_agent, evaluated_model
) -> None:
    context = delegation()
    access = EvaluationDataAccessContext(
        evaluation_access_request_id=uuid4(),
        tenant_id=context.tenant_id,
        organization_id=context.organization_id,
        on_behalf_of_user_id=context.on_behalf_of_user_id,
        service_actor_id=context.service_actor_id,
        agent_instance_id=context.agent_instance_id,
        task_id=context.task_id,
        evaluation_resource_id="benchmark-1",
        data_type=data_type,
        classification=DataClassification.CONFIDENTIAL,
        execution_tier=ExecutionTier.OFFLINE_EVALUATION,
        production_agent=production_agent,
        evaluated_model=evaluated_model,
        requested_at=NOW,
    )
    decision = evaluate_evaluation_data_access(
        access,
        EvaluationDataPolicyFacts(
            authorized_tenant_id=context.tenant_id,
            allowed_classifications=(DataClassification.CONFIDENTIAL,),
            explicit_data_type_authorizations=(data_type,),
        ),
        evaluation_access_decision_id=uuid4(),
        decided_at=NOW,
    )
    assert decision.outcome is EvaluationDataAccessOutcome.DENY
    assert decision.quarantine_trigger is QuarantineTriggerType.EVALUATION_DATA_ACCESS_ATTEMPT


def test_evaluation_access_requires_offline_tier_and_exact_tenant() -> None:
    context = delegation()
    access = EvaluationDataAccessContext(
        evaluation_access_request_id=uuid4(),
        tenant_id=context.tenant_id,
        organization_id=context.organization_id,
        on_behalf_of_user_id=context.on_behalf_of_user_id,
        service_actor_id=context.service_actor_id,
        agent_instance_id=context.agent_instance_id,
        task_id=context.task_id,
        evaluation_resource_id="benchmark-1",
        data_type=EvaluationDataType.EVALUATION_INPUT,
        classification=DataClassification.INTERNAL,
        execution_tier=ExecutionTier.IMMEDIATE_INTERACTIVE,
        production_agent=False,
        evaluated_model=False,
        requested_at=NOW,
    )
    decision = evaluate_evaluation_data_access(
        access,
        EvaluationDataPolicyFacts(
            authorized_tenant_id=uuid4(),
            allowed_classifications=(DataClassification.INTERNAL,),
            explicit_data_type_authorizations=(EvaluationDataType.EVALUATION_INPUT,),
        ),
        evaluation_access_decision_id=uuid4(),
        decided_at=NOW,
    )
    assert decision.outcome is EvaluationDataAccessOutcome.DENY


def test_audit_is_immutable_deterministic_and_contains_no_payload_fields() -> None:
    context = delegation()
    record = ZeroTrustAuditRecord(
        audit_id=uuid4(),
        event_type=ZeroTrustAuditEventType.DELEGATION_CREATED,
        tenant_id=context.tenant_id,
        organization_id=context.organization_id,
        on_behalf_of_user_id=context.on_behalf_of_user_id,
        service_actor_id=context.service_actor_id,
        agent_instance_id=context.agent_instance_id,
        task_id=context.task_id,
        delegation_id=context.delegation_id,
        result_code="created",
        occurred_at=NOW,
    )
    assert record.model_dump_json() == record.model_dump_json()
    forbidden = {
        "secret",
        "token",
        "prompt",
        "document_body",
        "raw_output",
        "hidden_label",
        "expected_output",
    }
    assert not forbidden & set(type(record).model_fields)
    with pytest.raises(ValidationError):
        record.result_code = "changed"

