"""Focused, network-free tests for Sprint 16 managed connector contracts."""

import inspect
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.runtime.ports import (
    RUNTIME_CONNECTOR_PROTOCOL_VERSION,
    RuntimeAdapterFamily,
    RuntimeConnectorDeliveryAcknowledgement,
    RuntimeConnectorDeliveryMaterializationFacts,
    RuntimeConnectorDeliveryWireRequest,
    RuntimeConnectorDeliveryWireResponse,
    RuntimeConnectorInvocationCapability,
    RuntimeConnectorInvocationCapabilityFactory,
    RuntimeConnectorMaterializationRequest,
    RuntimeConnectorObservationCapability,
    RuntimeConnectorObservationCapabilityFactory,
    RuntimeConnectorObservationInvocation,
    RuntimeConnectorObservationMaterializationFacts,
    RuntimeConnectorObservationMaterializationRequest,
    RuntimeConnectorOutcomeFactsProvider,
    RuntimeConnectorProvisioningCatalog,
    RuntimeConnectorProvisioningEntry,
    RuntimeCredentialLeaseReference,
    RuntimeCredentialLeaseRequest,
    RuntimeEffectClaim,
    RuntimeEffectDeliveryAttempt,
    RuntimeEffectDeliveryCertainty,
    RuntimeEffectDeliveryEnvelope,
    RuntimeEffectDeliveryInvocation,
    RuntimeEffectDeliveryResult,
    RuntimeEffectIdentity,
    RuntimeEffectReconciliationObservation,
    RuntimeEffectReconciliationOutcome,
    RuntimeEffectReconciliationRequest,
    RuntimeManagedConnectorInvocationCapability,
    RuntimeManagedConnectorObservationCapability,
    RuntimePortContractError,
    RuntimePortCredentialError,
    RuntimePortErrorCode,
    RuntimePortReconciliationError,
    RuntimePortScope,
    encode_runtime_connector_wire_request,
    parse_runtime_connector_delivery_response,
    runtime_connector_canonical_digest,
    validate_runtime_connector_delivery_acknowledgement,
    validate_runtime_connector_delivery_materialization_facts,
    validate_runtime_connector_delivery_result,
    validate_runtime_connector_delivery_wire_request,
    validate_runtime_connector_materialization_request,
    validate_runtime_connector_observation,
    validate_runtime_connector_observation_invocation,
    validate_runtime_connector_observation_materialization_facts,
    validate_runtime_connector_observation_materialization_request,
    validate_runtime_connector_provisioning_catalog,
)

NOW = datetime(2026, 8, 16, 4, 0, tzinfo=UTC)


def delivery_materialization_facts() -> RuntimeConnectorDeliveryMaterializationFacts:
    request = materialization()
    lease = request.credential_lease_request
    return RuntimeConnectorDeliveryMaterializationFacts(
        runtime_connector_materialization_request_id=(
            request.runtime_connector_materialization_request_id
        ),
        runtime_credential_lease_request_id=lease.runtime_credential_lease_request_id,
        connector_provisioning_reference=lease.connector_provisioning_reference,
        credential_reference=lease.credential_reference,
        credential_purpose_reference=lease.credential_purpose_reference,
        requested_at=request.requested_at,
        expires_at=lease.expires_at,
    )


def observation_materialization_facts() -> RuntimeConnectorObservationMaterializationFacts:
    request = observation_materialization()
    lease = request.credential_lease_request
    return RuntimeConnectorObservationMaterializationFacts(
        runtime_connector_observation_materialization_request_id=(
            request.runtime_connector_observation_materialization_request_id
        ),
        runtime_credential_lease_request_id=lease.runtime_credential_lease_request_id,
        connector_provisioning_reference=request.connector_provisioning_reference,
        credential_reference=lease.credential_reference,
        credential_purpose_reference=lease.credential_purpose_reference,
        requested_at=request.requested_at,
        expires_at=lease.expires_at,
    )


def uid(value: int) -> UUID:
    return UUID(int=value)


def scope() -> RuntimePortScope:
    return RuntimePortScope.model_construct(
        runtime_execution_request_id=uid(1),
        runtime_authority_bundle_id=uid(2),
        runtime_admission_decision_id=uid(3),
        execution_plan_id=uid(4),
        execution_plan_step_id=uid(5),
        attempt_id=uid(40),
        actor_id=uid(6),
        agent_instance_id=uid(7),
        on_behalf_of_user_id=None,
        tenant_id=uid(8),
        organization_id=uid(9),
        classification=DataClassification.CONFIDENTIAL,
        root_lineage_id=uid(10),
        root_lineage_digest_reference="digest.lineage",
        provenance_reference_ids=(),
        policy_revision=1,
        authorization_revision=1,
        registry_revision=1,
        state_revision=1,
    )


def identity() -> RuntimeEffectIdentity:
    return RuntimeEffectIdentity.model_construct(
        runtime_effect_id=uid(20),
        tenant_id=uid(8),
        organization_id=uid(9),
        runtime_execution_request_id=uid(1),
        execution_plan_id=uid(4),
        execution_plan_step_id=uid(5),
        payload_reference="payload.reference",
        payload_digest_reference="payload.digest",
        destination_reference="destination.approved",
        effect_idempotency_key="effect.idempotency",
        classification=DataClassification.CONFIDENTIAL,
        root_lineage_id=uid(10),
        root_lineage_digest_reference="digest.lineage",
    )


def envelope() -> RuntimeEffectDeliveryEnvelope:
    return RuntimeEffectDeliveryEnvelope.model_construct(
        runtime_effect_delivery_envelope_id=uid(30),
        effect_identity=identity(),
        adapter_family=RuntimeAdapterFamily.CONNECTOR,
        adapter_reference="adapter.connector",
        adapter_contract_version="1.0",
        actor_id=uid(6),
        agent_instance_id=uid(7),
        envelope_digest_reference="digest.envelope",
    )


def attempt() -> RuntimeEffectDeliveryAttempt:
    return RuntimeEffectDeliveryAttempt.model_construct(
        runtime_effect_delivery_attempt_id=uid(40),
        runtime_effect_id=uid(20),
        attempt_number=1,
        runtime_effect_claim_id=uid(42),
        lease_id=uid(43),
        runtime_authority_bundle_id=uid(2),
        runtime_admission_decision_id=uid(3),
        permit_reference_ids=(uid(50),),
        policy_revision=1,
        authorization_revision=1,
        registry_revision=1,
        state_revision=1,
        audit_revision=1,
        credential_lease_reference_id=uid(61),
        cancellation_reference_id=None,
        clock_reference="clock.trusted",
        requested_at=NOW,
        deadline=NOW + timedelta(minutes=5),
        attempt_digest_reference="digest.attempt",
    )


def claim() -> RuntimeEffectClaim:
    return RuntimeEffectClaim.model_construct(
        runtime_effect_claim_id=uid(42),
        runtime_effect_id=uid(20),
        tenant_id=uid(8),
        organization_id=uid(9),
        expected_lifecycle_revision=1,
        claimant_reference="worker.connector",
        lease_id=uid(43),
        clock_reference="clock.trusted",
        claimed_at=NOW - timedelta(seconds=1),
        expires_at=NOW + timedelta(minutes=5),
        claim_digest_reference="digest.claim",
    )


def invocation() -> RuntimeEffectDeliveryInvocation:
    return RuntimeEffectDeliveryInvocation.model_construct(
        runtime_effect_delivery_invocation_id=uid(41),
        envelope=envelope(),
        claim=claim(),
        attempt=attempt(),
    )


def lease_request() -> RuntimeCredentialLeaseRequest:
    return RuntimeCredentialLeaseRequest(
        runtime_credential_lease_request_id=uid(60),
        scope=scope(),
        adapter_family=RuntimeAdapterFamily.CONNECTOR,
        adapter_reference="adapter.connector",
        adapter_contract_version="1.0",
        connector_provisioning_reference="connector.provisioning",
        destination_reference="destination.approved",
        credential_reference="credential.reference",
        credential_purpose_reference="connector.invoke",
        permit_reference_ids=(uid(50),),
        runtime_effect_delivery_envelope_id=uid(30),
        envelope_digest_reference="digest.envelope",
        runtime_effect_id=uid(20),
        effect_idempotency_key="effect.idempotency",
        requested_at=NOW,
        expires_at=NOW + timedelta(minutes=4),
    )


def lease_reference() -> RuntimeCredentialLeaseReference:
    return RuntimeCredentialLeaseReference(
        runtime_credential_lease_reference_id=uid(61),
        runtime_credential_lease_request_id=uid(60),
        broker_reference="broker.production",
        runtime_execution_request_id=uid(1),
        adapter_family=RuntimeAdapterFamily.CONNECTOR,
        adapter_reference="adapter.connector",
        adapter_contract_version="1.0",
        connector_provisioning_reference="connector.provisioning",
        destination_reference="destination.approved",
        credential_reference="credential.reference",
        credential_purpose_reference="connector.invoke",
        permit_reference_ids=(uid(50),),
        runtime_effect_delivery_envelope_id=uid(30),
        envelope_digest_reference="digest.envelope",
        runtime_effect_id=uid(20),
        effect_idempotency_key="effect.idempotency",
        tenant_id=uid(8),
        organization_id=uid(9),
        actor_id=uid(6),
        agent_instance_id=uid(7),
        attempt_id=uid(40),
        classification=DataClassification.CONFIDENTIAL,
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=4),
    )


def materialization() -> RuntimeConnectorMaterializationRequest:
    return RuntimeConnectorMaterializationRequest(
        runtime_connector_materialization_request_id=uid(62),
        credential_lease_request=lease_request(),
        credential_lease_reference=lease_reference(),
        invocation=invocation(),
        requested_at=NOW + timedelta(seconds=1),
    )


def delivery_result(
    certainty: RuntimeEffectDeliveryCertainty,
    *,
    acknowledged: bool,
) -> RuntimeEffectDeliveryResult:
    delivered = certainty is RuntimeEffectDeliveryCertainty.DELIVERED
    return RuntimeEffectDeliveryResult(
        runtime_effect_delivery_result_id=uid(70),
        runtime_effect_id=uid(20),
        runtime_effect_delivery_attempt_id=uid(40),
        certainty=certainty,
        adapter_reference="adapter.connector",
        adapter_contract_version="1.0",
        result_reference="result.logical" if delivered else None,
        result_digest_reference="digest.result" if delivered else None,
        acknowledgement_reference="provider.operation" if acknowledged else None,
        acknowledgement_digest_reference="digest.acknowledgement" if acknowledged else None,
        failure_code=None if delivered else RuntimePortErrorCode.TIMEOUT,
        failure_reference=None if delivered else "failure.safe",
        started_at=NOW + timedelta(seconds=2),
        completed_at=NOW + timedelta(seconds=3),
        result_fact_digest_reference="digest.result-fact",
    )


def reconciliation_request() -> RuntimeEffectReconciliationRequest:
    return RuntimeEffectReconciliationRequest.model_construct(
        runtime_effect_reconciliation_request_id=uid(80),
        runtime_effect_id=uid(20),
        ambiguous_attempt_id=uid(40),
        ambiguous_result_id=uid(70),
        tenant_id=uid(8),
        organization_id=uid(9),
        destination_reference="destination.approved",
        connector_provisioning_reference="connector.provisioning",
        effect_idempotency_key="effect.idempotency",
        root_lineage_id=uid(10),
        root_lineage_digest_reference="digest.lineage",
        acknowledgement_reference="provider.operation",
        acknowledgement_digest_reference="digest.acknowledgement",
        observation_capability_reference="observation.connector",
        runtime_authority_bundle_id=uid(2),
        runtime_admission_decision_id=uid(3),
        permit_reference_ids=(uid(50),),
        classification=DataClassification.CONFIDENTIAL,
        clock_reference="clock.trusted",
        requested_at=NOW + timedelta(seconds=4),
        request_digest_reference="digest.reconciliation-request",
    )


def observation_invocation() -> RuntimeConnectorObservationInvocation:
    return RuntimeConnectorObservationInvocation(
        runtime_connector_observation_invocation_id=uid(81),
        envelope=envelope(),
        ambiguous_result=delivery_result(
            RuntimeEffectDeliveryCertainty.AMBIGUOUS,
            acknowledged=True,
        ),
        reconciliation_request=reconciliation_request(),
        requested_at=NOW + timedelta(seconds=4),
    )


def observation_lease_request() -> RuntimeCredentialLeaseRequest:
    return lease_request().model_copy(
        update={
            "runtime_credential_lease_request_id": uid(63),
            "credential_purpose_reference": "connector.observe",
            "requested_at": NOW + timedelta(seconds=4),
            "expires_at": NOW + timedelta(minutes=4),
        }
    )


def observation_lease_reference() -> RuntimeCredentialLeaseReference:
    return lease_reference().model_copy(
        update={
            "runtime_credential_lease_reference_id": uid(64),
            "runtime_credential_lease_request_id": uid(63),
            "credential_purpose_reference": "connector.observe",
            "issued_at": NOW + timedelta(seconds=4),
            "expires_at": NOW + timedelta(minutes=4),
        }
    )


def observation_materialization() -> RuntimeConnectorObservationMaterializationRequest:
    return RuntimeConnectorObservationMaterializationRequest(
        runtime_connector_observation_materialization_request_id=uid(65),
        credential_lease_request=observation_lease_request(),
        credential_lease_reference=observation_lease_reference(),
        connector_provisioning_reference="connector.provisioning",
        invocation=observation_invocation(),
        requested_at=NOW + timedelta(seconds=4),
    )


def observation() -> RuntimeEffectReconciliationObservation:
    request = reconciliation_request()
    return RuntimeEffectReconciliationObservation.model_construct(
        runtime_effect_reconciliation_observation_id=uid(82),
        runtime_effect_reconciliation_request_id=request.runtime_effect_reconciliation_request_id,
        runtime_effect_id=uid(20),
        tenant_id=uid(8),
        organization_id=uid(9),
        destination_reference="destination.approved",
        connector_provisioning_reference="connector.provisioning",
        effect_idempotency_key="effect.idempotency",
        root_lineage_id=uid(10),
        root_lineage_digest_reference="digest.lineage",
        acknowledgement_reference="provider.operation",
        acknowledgement_digest_reference="digest.acknowledgement",
        observation_capability_reference="observation.connector",
        runtime_authority_bundle_id=request.runtime_authority_bundle_id,
        permit_reference_ids=request.permit_reference_ids,
        classification=DataClassification.CONFIDENTIAL,
        outcome=RuntimeEffectReconciliationOutcome.STILL_AMBIGUOUS,
        observation_reference="provider.observation",
        observation_digest_reference="digest.observation",
        failure_reference=None,
        observed_at=NOW + timedelta(seconds=5),
    )


def test_materialization_is_exact_and_secret_free() -> None:
    request = materialization()
    assert validate_runtime_connector_materialization_request(request) is request
    fields = set(RuntimeCredentialLeaseReference.model_fields)
    assert not fields.intersection({"secret", "token", "password", "authorization_header"})

    substituted = request.model_copy(
        update={
            "credential_lease_reference": lease_reference().model_copy(
                update={"destination_reference": "destination.substituted"}
            )
        }
    )
    with pytest.raises(RuntimePortCredentialError):
        validate_runtime_connector_materialization_request(substituted)


def test_connector_result_mapping_preserves_ambiguity_and_rejects_false_certainty() -> None:
    request = materialization()
    delivered = delivery_result(RuntimeEffectDeliveryCertainty.DELIVERED, acknowledged=True)
    assert validate_runtime_connector_delivery_result(request, delivered) is delivered

    ambiguous = delivery_result(RuntimeEffectDeliveryCertainty.AMBIGUOUS, acknowledged=True)
    assert validate_runtime_connector_delivery_result(request, ambiguous) is ambiguous
    assert ambiguous.acknowledgement_reference == "provider.operation"

    with pytest.raises(ValidationError):
        delivery_result(
            RuntimeEffectDeliveryCertainty.DEFINITELY_NOT_DELIVERED,
            acknowledged=True,
        )
    with pytest.raises(ValidationError):
        RuntimeEffectDeliveryResult(
            **{
                **delivered.model_dump(),
                "acknowledgement_digest_reference": None,
            }
        )


def test_connector_observation_requires_exact_ambiguous_identity() -> None:
    invocation_fact = observation_invocation()
    assert validate_runtime_connector_observation_invocation(invocation_fact) is invocation_fact
    materialization_request = observation_materialization()
    assert (
        validate_runtime_connector_observation_materialization_request(materialization_request)
        is materialization_request
    )
    observed = observation()
    assert validate_runtime_connector_observation(materialization_request, observed) is observed

    substituted = invocation_fact.model_copy(
        update={
            "reconciliation_request": reconciliation_request().model_copy(
                update={"acknowledgement_reference": "provider.other"}
            )
        }
    )
    with pytest.raises(RuntimePortReconciliationError):
        validate_runtime_connector_observation_invocation(substituted)


def test_connector_observation_rejects_provisioning_time_and_delivery_lease_reuse() -> None:
    request = observation_materialization()
    with pytest.raises(RuntimePortCredentialError):
        validate_runtime_connector_observation_materialization_request(
            request.model_copy(update={"connector_provisioning_reference": "connector.other"})
        )
    with pytest.raises(RuntimePortCredentialError):
        validate_runtime_connector_observation_materialization_request(
            request.model_copy(update={"requested_at": NOW + timedelta(seconds=3)})
        )
    with pytest.raises(RuntimePortCredentialError):
        validate_runtime_connector_observation_materialization_request(
            request.model_copy(
                update={
                    "credential_lease_request": lease_request(),
                    "credential_lease_reference": lease_reference(),
                    "requested_at": NOW,
                }
            )
        )


def test_managed_protocols_are_runtime_checkable_and_have_closed_exit() -> None:
    class InvocationCapability:
        connector_provisioning_reference = "connector.provisioning"
        destination_reference = "destination.approved"
        runtime_credential_lease_reference_id = uid(61)

        async def invoke(self, invocation):
            return delivery_result(RuntimeEffectDeliveryCertainty.DELIVERED, acknowledged=True)

    class ManagedInvocation:
        async def __aenter__(self):
            return InvocationCapability()

        async def __aexit__(self, exc_type, exc_value, traceback):
            return False

    class InvocationFactory:
        def create(self, request):
            return ManagedInvocation()

    class ObservationCapability:
        connector_provisioning_reference = "connector.provisioning"
        destination_reference = "destination.approved"

        async def observe(self, invocation):
            return observation()

    class ManagedObservation:
        async def __aenter__(self):
            return ObservationCapability()

        async def __aexit__(self, exc_type, exc_value, traceback):
            return False

    class ObservationFactory:
        def create(self, request):
            return ManagedObservation()

    assert isinstance(InvocationCapability(), RuntimeConnectorInvocationCapability)
    assert isinstance(ManagedInvocation(), RuntimeManagedConnectorInvocationCapability)
    assert isinstance(InvocationFactory(), RuntimeConnectorInvocationCapabilityFactory)
    assert isinstance(ObservationCapability(), RuntimeConnectorObservationCapability)
    assert isinstance(ManagedObservation(), RuntimeManagedConnectorObservationCapability)
    assert isinstance(ObservationFactory(), RuntimeConnectorObservationCapabilityFactory)
    for managed in (
        RuntimeManagedConnectorInvocationCapability,
        RuntimeManagedConnectorObservationCapability,
    ):
        assert inspect.signature(managed.__aexit__).return_annotation == Literal[False]


def test_connector_contracts_are_strict_and_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        RuntimeConnectorMaterializationRequest(
            **{
                **materialization().model_dump(),
                "credential_secret": "forbidden",
            }
        )
    with pytest.raises(ValidationError):
        RuntimeCredentialLeaseRequest(
            **{
                **lease_request().model_dump(),
                "adapter_family": RuntimeAdapterFamily.PROVIDER,
            }
        )
    with pytest.raises(ValidationError):
        RuntimeConnectorObservationMaterializationRequest(
            **{
                **observation_materialization().model_dump(),
                "credential_secret": "forbidden",
            }
        )


def test_connector_result_binding_rejects_adapter_substitution() -> None:
    result = delivery_result(RuntimeEffectDeliveryCertainty.DELIVERED, acknowledged=True)
    substituted = result.model_copy(update={"adapter_reference": "adapter.other"})
    with pytest.raises(RuntimePortContractError):
        validate_runtime_connector_delivery_result(materialization(), substituted)


def delivery_wire_request() -> RuntimeConnectorDeliveryWireRequest:
    source = materialization()
    invocation = source.invocation
    envelope = invocation.envelope
    identity = envelope.effect_identity
    return RuntimeConnectorDeliveryWireRequest(
        protocol_version=RUNTIME_CONNECTOR_PROTOCOL_VERSION,
        operation="deliver",
        runtime_effect_id=identity.runtime_effect_id,
        runtime_execution_request_id=identity.runtime_execution_request_id,
        runtime_effect_delivery_attempt_id=invocation.attempt.runtime_effect_delivery_attempt_id,
        runtime_effect_delivery_invocation_id=invocation.runtime_effect_delivery_invocation_id,
        runtime_effect_delivery_envelope_id=envelope.runtime_effect_delivery_envelope_id,
        payload_reference=identity.payload_reference,
        payload_digest_reference=identity.payload_digest_reference,
        destination_reference=identity.destination_reference,
        connector_provisioning_reference=(
            source.credential_lease_request.connector_provisioning_reference
        ),
        adapter_reference=envelope.adapter_reference,
        adapter_contract_version=envelope.adapter_contract_version,
        effect_idempotency_key=identity.effect_idempotency_key,
        tenant_id=identity.tenant_id,
        organization_id=identity.organization_id,
        classification=identity.classification,
        root_lineage_id=identity.root_lineage_id,
        root_lineage_digest_reference=identity.root_lineage_digest_reference,
        permit_reference_ids=invocation.attempt.permit_reference_ids,
    )


def test_connector_wire_request_is_exact_and_canonically_encoded() -> None:
    request = delivery_wire_request()
    assert validate_runtime_connector_delivery_wire_request(materialization(), request) is request
    body = encode_runtime_connector_wire_request(request)
    assert body.startswith(b'{"protocol_version":"policyos-runtime-connector-v1"')
    assert b"credential" not in body and b"Authorization" not in body
    assert runtime_connector_canonical_digest((uid(1), NOW, 1, (uid(2),))) == (
        runtime_connector_canonical_digest((uid(1), NOW, 1, (uid(2),)))
    )
    with pytest.raises(RuntimePortContractError):
        validate_runtime_connector_delivery_wire_request(
            materialization(), request.model_copy(update={"destination_reference": "other"})
        )


def test_connector_acknowledgement_requires_exact_200_identity_time_and_digest() -> None:
    request = delivery_wire_request()
    acknowledgement = RuntimeConnectorDeliveryAcknowledgement(
        protocol_version=RUNTIME_CONNECTOR_PROTOCOL_VERSION,
        operation_reference="provider.operation.1",
        runtime_effect_id=request.runtime_effect_id,
        runtime_effect_delivery_attempt_id=request.runtime_effect_delivery_attempt_id,
        destination_reference=request.destination_reference,
        effect_idempotency_key=request.effect_idempotency_key,
        accepted_at=NOW + timedelta(seconds=1),
        acknowledgement_digest_reference="digest.placeholder",
    )
    projection = tuple(
        getattr(acknowledgement, name) for name in tuple(type(acknowledgement).model_fields)[:-1]
    )
    acknowledgement = acknowledgement.model_copy(
        update={"acknowledgement_digest_reference": runtime_connector_canonical_digest(projection)}
    )
    response = RuntimeConnectorDeliveryWireResponse(delivery_acknowledgement=acknowledgement)
    assert (
        parse_runtime_connector_delivery_response(response.model_dump_json().encode("utf-8"))
        == response
    )
    assert (
        validate_runtime_connector_delivery_acknowledgement(
            request,
            response,
            http_status=200,
            trusted_started_at=NOW,
            trusted_completed_at=NOW + timedelta(seconds=2),
        )
        is acknowledgement
    )
    with pytest.raises(RuntimePortContractError):
        validate_runtime_connector_delivery_acknowledgement(
            request,
            response,
            http_status=201,
            trusted_started_at=NOW,
            trusted_completed_at=NOW + timedelta(seconds=2),
        )


def test_connector_response_parser_rejects_duplicate_unknown_bom_and_oversize() -> None:
    duplicate = b'{"delivery_acknowledgement":{},"delivery_acknowledgement":{}}'
    with pytest.raises(RuntimePortContractError):
        parse_runtime_connector_delivery_response(duplicate)
    with pytest.raises(RuntimePortContractError):
        parse_runtime_connector_delivery_response(b"\xef\xbb\xbf{}")
    with pytest.raises(RuntimePortContractError):
        parse_runtime_connector_delivery_response(b"{" + b" " * 16_384 + b"}")


def test_outcome_facts_provider_is_runtime_checkable_without_secret_surface() -> None:
    class Provider:
        def delivery_facts(self, request):
            raise NotImplementedError

        def observation_facts(self, request):
            raise NotImplementedError

    assert isinstance(Provider(), RuntimeConnectorOutcomeFactsProvider)
    fields = set(RuntimeConnectorDeliveryWireRequest.model_fields)
    assert not fields.intersection({"credential", "secret", "authorization", "token"})


def test_materialization_facts_are_strict_frozen_and_exactly_bound() -> None:
    delivery = delivery_materialization_facts()
    observed = observation_materialization_facts()

    assert (
        validate_runtime_connector_delivery_materialization_facts(delivery, materialization())
        is delivery
    )
    assert (
        validate_runtime_connector_observation_materialization_facts(
            observed, observation_materialization()
        )
        is observed
    )
    with pytest.raises(ValidationError):
        RuntimeConnectorDeliveryMaterializationFacts.model_validate(
            {**delivery.model_dump(), "unexpected": "forbidden"}
        )
    with pytest.raises(ValidationError):
        RuntimeConnectorDeliveryMaterializationFacts(
            **{**delivery.model_dump(), "expires_at": delivery.requested_at}
        )
    with pytest.raises(RuntimePortCredentialError):
        validate_runtime_connector_delivery_materialization_facts(
            delivery.model_copy(update={"credential_reference": "credential.substituted"}),
            materialization(),
        )


def test_provisioning_catalog_requires_one_canonical_https_entry() -> None:
    entry = RuntimeConnectorProvisioningEntry(
        connector_provisioning_reference="connector.provisioning",
        adapter_reference="adapter.connector",
        adapter_contract_version="1.0",
        destination_reference="destination.approved",
        endpoint_uri="https://connector.policyos.example/v1/runtime",
        tenant_id=uid(8),
        organization_id=uid(9),
        classification_ceiling=DataClassification.CONFIDENTIAL,
        credential_reference="credential.reference",
        delivery_credential_purpose_reference="connector.invoke",
        observation_credential_purpose_reference="connector.observe",
        enabled=True,
    )
    catalog = RuntimeConnectorProvisioningCatalog(entries=(entry,))
    assert validate_runtime_connector_provisioning_catalog(catalog) is catalog

    with pytest.raises(RuntimePortContractError):
        validate_runtime_connector_provisioning_catalog(
            RuntimeConnectorProvisioningCatalog(entries=())
        )
    with pytest.raises(RuntimePortContractError):
        validate_runtime_connector_provisioning_catalog(
            RuntimeConnectorProvisioningCatalog(
                entries=(entry.model_copy(update={"endpoint_uri": "http://example.test"}),)
            )
        )
    for update in (
        {"delivery_credential_purpose_reference": "connector.observe"},
        {"observation_credential_purpose_reference": "connector.invoke"},
    ):
        with pytest.raises(ValidationError):
            RuntimeConnectorProvisioningEntry(**(entry.model_dump() | update))
        with pytest.raises(RuntimePortContractError):
            validate_runtime_connector_provisioning_catalog(
                RuntimeConnectorProvisioningCatalog(entries=(entry.model_copy(update=update),))
            )
