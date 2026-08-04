"""Pure tests for the CP8 effect-delivery contract governance gate."""

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.runtime.authority import (
    RuntimeAdmissionDecision,
    RuntimeAuthorityBundle,
    RuntimeAuthorityDecisionStatus,
    RuntimeExecutionEnvironment,
    RuntimeExecutionRequest,
    RuntimePermitReference,
    RuntimePermitStatus,
    RuntimeRiskLevel,
)
from app.runtime.orchestration import (
    RuntimeOrchestrationContractVersion,
    RuntimeOrchestrationDeliveryRequest,
    validate_runtime_orchestration_delivery_request,
)
from app.runtime.ports import (
    RuntimeAdapterFamily,
    RuntimeEffectClaim,
    RuntimeEffectDeadLetterRecord,
    RuntimeEffectDeliveryAttempt,
    RuntimeEffectDeliveryCertainty,
    RuntimeEffectDeliveryEnvelope,
    RuntimeEffectDeliveryInvocation,
    RuntimeEffectDeliveryPort,
    RuntimeEffectDeliveryResult,
    RuntimeEffectIdentity,
    RuntimeEffectLifecycleRecord,
    RuntimeEffectLifecycleRepository,
    RuntimeEffectLifecycleStatus,
    RuntimeEffectObservationPort,
    RuntimeEffectReconciliationObservation,
    RuntimeEffectReconciliationOutcome,
    RuntimeEffectReconciliationRequest,
    RuntimeEffectRetryDecision,
    RuntimeEffectRetryDecisionStatus,
    RuntimePortClaimError,
    RuntimePortContractVersion,
    RuntimePortEffectConflictError,
    RuntimePortErrorCode,
    RuntimePortLifecycleError,
    RuntimePortRetryError,
    validate_runtime_effect_claim,
    validate_runtime_effect_delivery_attempt,
    validate_runtime_effect_delivery_result,
    validate_runtime_effect_identity,
    validate_runtime_effect_lifecycle_transition,
    validate_runtime_effect_reconciliation,
    validate_runtime_effect_retry_decision,
)
from app.runtime.registry import RuntimeActionSideEffectLevel

NOW = datetime(2026, 8, 3, 9, 0, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[1]


def uid(value: int) -> UUID:
    return UUID(int=value)


def port_contract() -> RuntimePortContractVersion:
    return RuntimePortContractVersion(
        runtime_ports_version="1.0",
        runtime_ports_contract_version="1.0",
        runtime_ports_schema_version="1.0",
    )


def orchestration_contract() -> RuntimeOrchestrationContractVersion:
    return RuntimeOrchestrationContractVersion(
        runtime_orchestration_version="1.0",
        runtime_orchestration_contract_version="1.0",
        runtime_orchestration_schema_version="1.0",
    )


def effect_identity(**updates) -> RuntimeEffectIdentity:
    values = {
        "runtime_effect_id": uid(1),
        "tenant_id": uid(2),
        "organization_id": uid(3),
        "runtime_execution_request_id": uid(4),
        "execution_plan_id": uid(5),
        "execution_plan_step_id": uid(6),
        "action_definition_id": "action.send",
        "action": "send",
        "action_version": "1.0",
        "destination_reference": "destination.approved",
        "payload_schema_reference": "schema.payload",
        "payload_reference": "payload.opaque",
        "payload_digest_reference": "digest.payload",
        "effect_idempotency_key": "effect-key-1",
        "classification": DataClassification.CONFIDENTIAL,
        "root_lineage_id": uid(7),
        "root_lineage_digest_reference": "digest.lineage",
        "provenance_reference_ids": (uid(8), uid(9)),
        "originating_outbox_enqueue_record_id": uid(10),
        "originating_transaction_id": uid(11),
        "originating_transaction_receipt_id": uid(12),
        "effect_fingerprint_digest_reference": "digest.effect",
    }
    values.update(updates)
    return RuntimeEffectIdentity(**values)


def delivery_envelope(**updates) -> RuntimeEffectDeliveryEnvelope:
    values = {
        "runtime_effect_delivery_envelope_id": uid(20),
        "contract_version": port_contract(),
        "effect_identity": effect_identity(),
        "adapter_family": RuntimeAdapterFamily.PROVIDER,
        "adapter_reference": "adapter.provider",
        "adapter_contract_version": "1.0",
        "runtime_registry_snapshot_id": uid(21),
        "runtime_action_resolution_decision_id": uid(22),
        "runtime_registry_snapshot_entry_id": uid(23),
        "input_schema_reference": "schema.payload",
        "output_schema_reference": "schema.result",
        "resource_reference": "resource.document",
        "purpose": "purpose.send",
        "execution_environment": RuntimeExecutionEnvironment.EXTERNAL,
        "risk_level": RuntimeRiskLevel.MODERATE,
        "side_effect_level": RuntimeActionSideEffectLevel.EXTERNAL_TRANSMISSION,
        "side_effect_level_reference": "side-effect.transmit",
        "actor_id": uid(24),
        "agent_instance_id": uid(25),
        "on_behalf_of_user_id": uid(26),
        "originating_state_record_id": uid(27),
        "originating_state_revision": 4,
        "originating_audit_trail_id": uid(28),
        "originating_audit_event_id": uid(29),
        "originating_audit_revision": 5,
        "retry_policy_reference": "retry.policy",
        "retry_eligible": True,
        "maximum_attempt_count": 3,
        "deadline_policy_reference": "deadline.policy",
        "envelope_digest_reference": "digest.envelope",
        "created_at": NOW,
    }
    values.update(updates)
    return RuntimeEffectDeliveryEnvelope(**values)


def claim(**updates) -> RuntimeEffectClaim:
    values = {
        "runtime_effect_claim_id": uid(30),
        "runtime_effect_id": uid(1),
        "tenant_id": uid(2),
        "organization_id": uid(3),
        "expected_lifecycle_revision": 1,
        "claimant_reference": "worker.reference",
        "lease_id": uid(31),
        "clock_reference": "clock.delivery",
        "claimed_at": NOW + timedelta(seconds=1),
        "expires_at": NOW + timedelta(minutes=5),
        "claim_digest_reference": "digest.claim",
    }
    values.update(updates)
    return RuntimeEffectClaim(**values)


def attempt(**updates) -> RuntimeEffectDeliveryAttempt:
    values = {
        "runtime_effect_delivery_attempt_id": uid(40),
        "runtime_effect_id": uid(1),
        "attempt_number": 1,
        "runtime_effect_claim_id": uid(30),
        "lease_id": uid(31),
        "runtime_authority_bundle_id": uid(50),
        "runtime_admission_decision_id": uid(51),
        "permit_reference_ids": (uid(52),),
        "policy_revision": 2,
        "authorization_revision": 3,
        "registry_revision": 4,
        "state_revision": 5,
        "audit_revision": 6,
        "credential_lease_reference_id": None,
        "cancellation_reference_id": None,
        "clock_reference": "clock.delivery",
        "requested_at": NOW + timedelta(seconds=2),
        "deadline": NOW + timedelta(minutes=4),
        "attempt_digest_reference": "digest.attempt",
    }
    values.update(updates)
    return RuntimeEffectDeliveryAttempt(**values)


def delivery_result(
    certainty: RuntimeEffectDeliveryCertainty = RuntimeEffectDeliveryCertainty.DELIVERED,
    **updates,
) -> RuntimeEffectDeliveryResult:
    delivered = certainty is RuntimeEffectDeliveryCertainty.DELIVERED
    values = {
        "runtime_effect_delivery_result_id": uid(60),
        "runtime_effect_id": uid(1),
        "runtime_effect_delivery_attempt_id": uid(40),
        "certainty": certainty,
        "adapter_reference": "adapter.provider",
        "adapter_contract_version": "1.0",
        "result_reference": "result.ref" if delivered else None,
        "result_digest_reference": "digest.result" if delivered else None,
        "acknowledgement_reference": "ack.ref" if delivered else None,
        "acknowledgement_digest_reference": "digest.ack" if delivered else None,
        "failure_code": None if delivered else RuntimePortErrorCode.TIMEOUT,
        "failure_reference": None if delivered else "failure.safe",
        "started_at": NOW + timedelta(seconds=3),
        "completed_at": NOW + timedelta(seconds=4),
        "result_fact_digest_reference": "digest.result-fact",
    }
    values.update(updates)
    return RuntimeEffectDeliveryResult(**values)


def lifecycle(
    revision: int = 1,
    status: RuntimeEffectLifecycleStatus = RuntimeEffectLifecycleStatus.ENQUEUED,
    **updates,
) -> RuntimeEffectLifecycleRecord:
    values = {
        "runtime_effect_lifecycle_record_id": uid(70 + revision),
        "runtime_effect_id": uid(1),
        "lifecycle_revision": revision,
        "status": status,
        "previous_lifecycle_record_id": None if revision == 1 else uid(69 + revision),
        "previous_lifecycle_digest_reference": (
            None if revision == 1 else f"digest.lifecycle-{revision - 1}"
        ),
        "runtime_effect_claim_id": uid(30)
        if status
        in {
            RuntimeEffectLifecycleStatus.CLAIMED,
            RuntimeEffectLifecycleStatus.DELIVERING,
        }
        else None,
        "runtime_effect_delivery_attempt_id": uid(40)
        if status
        in {
            RuntimeEffectLifecycleStatus.DELIVERING,
            RuntimeEffectLifecycleStatus.DELIVERED,
            RuntimeEffectLifecycleStatus.RETRY_SCHEDULED,
            RuntimeEffectLifecycleStatus.AMBIGUOUS,
        }
        else None,
        "runtime_effect_delivery_result_id": uid(60)
        if status
        in {
            RuntimeEffectLifecycleStatus.DELIVERED,
            RuntimeEffectLifecycleStatus.AMBIGUOUS,
        }
        else None,
        "runtime_effect_retry_decision_id": uid(80)
        if status is RuntimeEffectLifecycleStatus.RETRY_SCHEDULED
        else None,
        "runtime_effect_reconciliation_observation_id": None,
        "runtime_effect_dead_letter_record_id": uid(81)
        if status is RuntimeEffectLifecycleStatus.DEAD_LETTERED
        else None,
        "recorded_at": NOW + timedelta(seconds=revision),
        "lifecycle_digest_reference": f"digest.lifecycle-{revision}",
    }
    values.update(updates)
    return RuntimeEffectLifecycleRecord(**values)


def retry_decision(**updates) -> RuntimeEffectRetryDecision:
    values = {
        "runtime_effect_retry_decision_id": uid(80),
        "runtime_effect_id": uid(1),
        "prior_attempt_id": uid(40),
        "next_attempt_id": uid(41),
        "decision_status": RuntimeEffectRetryDecisionStatus.APPROVED,
        "retry_policy_reference": "retry.policy",
        "maximum_attempt_count": 3,
        "completed_attempt_count": 1,
        "prior_certainty": RuntimeEffectDeliveryCertainty.DEFINITELY_NOT_DELIVERED,
        "reconciliation_observation_id": None,
        "reconciliation_outcome": None,
        "effect_fingerprint_digest_reference": "digest.effect",
        "runtime_authority_bundle_id": uid(50),
        "runtime_admission_decision_id": uid(51),
        "permit_reference_ids": (uid(52),),
        "side_effect_level": RuntimeActionSideEffectLevel.EXTERNAL_TRANSMISSION,
        "automatic": False,
        "eligible_at": NOW + timedelta(minutes=1),
        "decided_at": NOW + timedelta(seconds=5),
        "retry_decision_digest_reference": "digest.retry",
    }
    values.update(updates)
    return RuntimeEffectRetryDecision(**values)


def reconciliation_request() -> RuntimeEffectReconciliationRequest:
    return RuntimeEffectReconciliationRequest(
        runtime_effect_reconciliation_request_id=uid(90),
        runtime_effect_id=uid(1),
        ambiguous_attempt_id=uid(40),
        ambiguous_result_id=uid(60),
        tenant_id=uid(2),
        organization_id=uid(3),
        destination_reference="destination.approved",
        observation_capability_reference="observation.provider",
        runtime_authority_bundle_id=uid(50),
        runtime_admission_decision_id=uid(51),
        permit_reference_ids=(uid(52),),
        classification=DataClassification.CONFIDENTIAL,
        clock_reference="clock.delivery",
        requested_at=NOW + timedelta(minutes=1),
        request_digest_reference="digest.reconciliation-request",
    )


def observation(
    outcome: RuntimeEffectReconciliationOutcome = (
        RuntimeEffectReconciliationOutcome.CONFIRMED_NOT_DELIVERED
    ),
) -> RuntimeEffectReconciliationObservation:
    unavailable = outcome is RuntimeEffectReconciliationOutcome.OBSERVATION_UNAVAILABLE
    return RuntimeEffectReconciliationObservation(
        runtime_effect_reconciliation_observation_id=uid(91),
        runtime_effect_reconciliation_request_id=uid(90),
        runtime_effect_id=uid(1),
        tenant_id=uid(2),
        organization_id=uid(3),
        destination_reference="destination.approved",
        observation_capability_reference="observation.provider",
        runtime_authority_bundle_id=uid(50),
        permit_reference_ids=(uid(52),),
        outcome=outcome,
        observation_reference=None if unavailable else "observation.ref",
        observation_digest_reference=None if unavailable else "digest.observation",
        failure_reference="observation.unavailable" if unavailable else None,
        classification=DataClassification.CONFIDENTIAL,
        observed_at=NOW + timedelta(minutes=1, seconds=1),
    )


def authority_bundle() -> RuntimeAuthorityBundle:
    request = RuntimeExecutionRequest.model_construct(runtime_execution_request_id=uid(4))
    admission = RuntimeAdmissionDecision.model_construct(
        runtime_admission_decision_id=uid(51),
        decision_status=RuntimeAuthorityDecisionStatus.ADMITTED,
        permit_reference_ids=(uid(52),),
    )
    permit = RuntimePermitReference.model_construct(
        runtime_permit_reference_id=uid(52),
        permit_status=RuntimePermitStatus.ACTIVE,
        valid_from=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=10),
        remaining_invocations=1,
        remaining_attempts=2,
        runtime_execution_request_id=uid(4),
        tenant_id=uid(2),
        organization_id=uid(3),
        actor_id=uid(24),
        resource_reference="resource.document",
        action="send",
        purpose="purpose.send",
        destination_reference="destination.approved",
        execution_environment=RuntimeExecutionEnvironment.EXTERNAL,
        risk_level=RuntimeRiskLevel.MODERATE,
        classification_ceiling=DataClassification.CONFIDENTIAL,
    )
    return RuntimeAuthorityBundle.model_construct(
        runtime_authority_bundle_id=uid(50),
        execution_request=request,
        admission_decision=admission,
        permit_references=(permit,),
        tenant_id=uid(2),
        organization_id=uid(3),
        classification=DataClassification.CONFIDENTIAL,
        root_lineage_id=uid(7),
        root_lineage_digest_reference="digest.lineage",
        policy_revision=2,
        authorization_revision=3,
        registry_revision=4,
    )


def test_effect_identity_is_stable_across_attempts_and_fails_closed() -> None:
    fields = RuntimeEffectIdentity.model_fields
    assert "attempt_id" not in fields
    assert "runtime_effect_claim_id" not in fields
    validate_runtime_effect_identity(effect_identity(), effect_identity())
    with pytest.raises(RuntimePortEffectConflictError):
        validate_runtime_effect_identity(
            effect_identity(),
            effect_identity(destination_reference="destination.changed"),
        )
    with pytest.raises(ValidationError):
        effect_identity(attempt_id=uid(99))


def test_claim_requires_exact_revision_and_no_overlapping_lease() -> None:
    first = lifecycle()
    validate_runtime_effect_claim(
        first,
        claim(),
        identity=effect_identity(),
        observed_at=NOW + timedelta(seconds=2),
    )
    claimed = lifecycle(2, RuntimeEffectLifecycleStatus.CLAIMED)
    with pytest.raises(RuntimePortClaimError):
        validate_runtime_effect_claim(
            claimed,
            claim(
                runtime_effect_claim_id=uid(32),
                lease_id=uid(33),
                expected_lifecycle_revision=2,
                claimed_at=NOW + timedelta(minutes=2),
                expires_at=NOW + timedelta(minutes=6),
            ),
            identity=effect_identity(),
            observed_at=NOW + timedelta(minutes=2, seconds=1),
            previous_claim=claim(),
        )


def test_delivery_attempt_and_certainty_are_bounded() -> None:
    validate_runtime_effect_delivery_attempt(delivery_envelope(), claim(), attempt())
    validate_runtime_effect_delivery_result(
        delivery_envelope(), attempt(), delivery_result()
    )
    with pytest.raises(ValidationError):
        delivery_result(
            RuntimeEffectDeliveryCertainty.AMBIGUOUS,
            result_reference="unsafe-result",
            result_digest_reference="unsafe-digest",
        )
    with pytest.raises(RuntimePortRetryError):
        validate_runtime_effect_delivery_attempt(
            delivery_envelope(), claim(), attempt(attempt_number=4)
        )


def test_lifecycle_graph_is_closed_append_only_and_terminal() -> None:
    enqueued = lifecycle()
    claimed = lifecycle(2, RuntimeEffectLifecycleStatus.CLAIMED)
    validate_runtime_effect_lifecycle_transition(enqueued, claimed)
    delivering = lifecycle(3, RuntimeEffectLifecycleStatus.DELIVERING)
    validate_runtime_effect_lifecycle_transition(claimed, delivering)
    delivered = lifecycle(4, RuntimeEffectLifecycleStatus.DELIVERED)
    validate_runtime_effect_lifecycle_transition(delivering, delivered)
    with pytest.raises(RuntimePortLifecycleError):
        validate_runtime_effect_lifecycle_transition(
            delivered,
            lifecycle(5, RuntimeEffectLifecycleStatus.CLAIMED),
        )


def test_ambiguous_delivery_needs_reconciliation_before_retry() -> None:
    ambiguous = delivery_result(RuntimeEffectDeliveryCertainty.AMBIGUOUS)
    decision = retry_decision(
        prior_certainty=RuntimeEffectDeliveryCertainty.AMBIGUOUS,
        reconciliation_observation_id=uid(91),
        reconciliation_outcome=(
            RuntimeEffectReconciliationOutcome.CONFIRMED_NOT_DELIVERED
        ),
    )
    with pytest.raises(RuntimePortRetryError):
        validate_runtime_effect_retry_decision(
            effect_identity(),
            delivery_envelope(),
            ambiguous,
            decision,
            observed_at=NOW + timedelta(minutes=2),
        )
    validate_runtime_effect_retry_decision(
        effect_identity(),
        delivery_envelope(),
        ambiguous,
        decision,
        observed_at=NOW + timedelta(minutes=2),
        observation=observation(),
    )
    ambiguous_record = lifecycle(2, RuntimeEffectLifecycleStatus.AMBIGUOUS)
    with pytest.raises(RuntimePortLifecycleError):
        validate_runtime_effect_lifecycle_transition(
            ambiguous_record,
            lifecycle(3, RuntimeEffectLifecycleStatus.RETRY_SCHEDULED),
        )
    validate_runtime_effect_lifecycle_transition(
        ambiguous_record,
        lifecycle(
            3,
            RuntimeEffectLifecycleStatus.RETRY_SCHEDULED,
            runtime_effect_reconciliation_observation_id=uid(91),
        ),
    )


def test_retry_is_bounded_and_sensitive_actions_do_not_retry_automatically() -> None:
    with pytest.raises(ValidationError):
        retry_decision(completed_attempt_count=3)
    with pytest.raises(ValidationError):
        retry_decision(
            side_effect_level=RuntimeActionSideEffectLevel.PUBLICATION,
            automatic=True,
        )
    denied = retry_decision(
        decision_status=RuntimeEffectRetryDecisionStatus.DENIED,
        next_attempt_id=None,
        eligible_at=None,
    )
    assert denied.decision_status is RuntimeEffectRetryDecisionStatus.DENIED


def test_dead_letter_is_terminal_reference_only_evidence() -> None:
    record = RuntimeEffectDeadLetterRecord(
        runtime_effect_dead_letter_record_id=uid(100),
        runtime_effect_id=uid(1),
        tenant_id=uid(2),
        organization_id=uid(3),
        terminal_lifecycle_revision=4,
        attempt_reference_ids=(uid(40), uid(41)),
        safe_failure_code=RuntimePortErrorCode.OUTBOX_FAILURE,
        safe_failure_reference="failure.safe",
        policy_reference="policy.delivery",
        runtime_authority_bundle_id=uid(50),
        classification=DataClassification.CONFIDENTIAL,
        root_lineage_id=uid(7),
        root_lineage_digest_reference="digest.lineage",
        terminal_reason_reference="terminal.exhausted",
        dead_lettered_at=NOW + timedelta(minutes=3),
        dead_letter_digest_reference="digest.dead-letter",
    )
    assert not any(
        "payload" in name or "credential" in name
        for name in type(record).model_fields
    )
    dead = lifecycle(2, RuntimeEffectLifecycleStatus.DEAD_LETTERED)
    with pytest.raises(RuntimePortLifecycleError):
        validate_runtime_effect_lifecycle_transition(
            dead,
            lifecycle(3, RuntimeEffectLifecycleStatus.CLAIMED),
        )


def test_reconciliation_never_infers_success_from_unavailable_observation() -> None:
    unavailable = observation(RuntimeEffectReconciliationOutcome.OBSERVATION_UNAVAILABLE)
    validate_runtime_effect_reconciliation(reconciliation_request(), unavailable)
    assert unavailable.outcome is RuntimeEffectReconciliationOutcome.OBSERVATION_UNAVAILABLE
    with pytest.raises(ValidationError):
        RuntimeEffectReconciliationObservation(
            **{
                **unavailable.model_dump(),
                "outcome": RuntimeEffectReconciliationOutcome.CONFIRMED_DELIVERED,
            }
        )


def test_orchestration_delivery_request_revalidates_current_authority() -> None:
    request = RuntimeOrchestrationDeliveryRequest(
        runtime_orchestration_delivery_id=uid(110),
        contract_version=orchestration_contract(),
        authority=authority_bundle(),
        envelope=delivery_envelope(),
        claim=claim(),
        attempt=attempt(),
        clock_reference="clock.delivery",
        cancellation_reference=None,
        credential_lease_request=None,
        requested_at=NOW + timedelta(seconds=2),
    )
    validate_runtime_orchestration_delivery_request(request)


def test_delivery_protocols_are_structural_and_do_not_grant_authority() -> None:
    class FakeDelivery:
        adapter_reference = "adapter.provider"
        adapter_contract_version = "1.0"
        adapter_family = RuntimeAdapterFamily.PROVIDER

        async def deliver(self, invocation: RuntimeEffectDeliveryInvocation):
            return delivery_result()

    class FakeObservation:
        observation_capability_reference = "observation.provider"

        async def observe(self, request: RuntimeEffectReconciliationRequest):
            return observation()

    class FakeRepository:
        async def get(self, request):
            return None

        async def append(self, record, request, *, stored_at):
            return None

        async def claim(self, claim, record, request, *, stored_at):
            return None

    assert isinstance(FakeDelivery(), RuntimeEffectDeliveryPort)
    assert isinstance(FakeObservation(), RuntimeEffectObservationPort)
    assert isinstance(FakeRepository(), RuntimeEffectLifecycleRepository)
    assert "authority" not in RuntimeEffectClaim.model_fields
    assert "permit_reference_ids" not in RuntimeEffectClaim.model_fields


def test_delivery_gate_has_no_io_or_forbidden_dependency() -> None:
    files = (
        ROOT / "app" / "runtime" / "ports" / "delivery.py",
        ROOT / "app" / "runtime" / "ports" / "delivery_protocols.py",
        ROOT / "app" / "runtime" / "ports" / "delivery_validation.py",
        ROOT / "app" / "runtime" / "orchestration" / "delivery_domain.py",
        ROOT / "app" / "runtime" / "orchestration" / "delivery_validation.py",
    )
    forbidden_imports = {
        "sqlalchemy",
        "redis",
        "fastapi",
        "subprocess",
        "importlib",
        "requests",
        "httpx",
        "app.runtime.persistence",
        "app.runtime.adapters",
    }
    forbidden_calls = {"uuid4", "now", "utcnow", "sleep", "open"}
    for source in files:
        tree = ast.parse(source.read_text(encoding="utf-8"))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        } | {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        assert not any(
            imported == forbidden or imported.startswith(f"{forbidden}.")
            for imported in imports
            for forbidden in forbidden_imports
        )
        calls = {
            node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Attribute, ast.Name))
        }
        assert not calls.intersection(forbidden_calls)
    assert not (ROOT / "app" / "runtime" / "outbox").exists()
