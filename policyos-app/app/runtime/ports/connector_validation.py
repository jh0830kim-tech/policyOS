"""Pure exact-binding validation for managed connector contracts."""

from app.runtime.ports.connector import (
    RuntimeConnectorMaterializationRequest,
    RuntimeConnectorObservationInvocation,
    RuntimeConnectorObservationMaterializationRequest,
)
from app.runtime.ports.delivery import (
    RuntimeEffectDeliveryCertainty,
    RuntimeEffectDeliveryResult,
    RuntimeEffectReconciliationObservation,
)
from app.runtime.ports.delivery_validation import (
    validate_runtime_effect_delivery_result,
    validate_runtime_effect_reconciliation,
)
from app.runtime.ports.domain import RuntimeAdapterFamily
from app.runtime.ports.errors import (
    RuntimePortContractError,
    RuntimePortCredentialError,
    RuntimePortReconciliationError,
)
from app.runtime.ports.validation import validate_runtime_credential_lease_reference


def validate_runtime_connector_materialization_request(
    request: RuntimeConnectorMaterializationRequest,
) -> RuntimeConnectorMaterializationRequest:
    lease_request = request.credential_lease_request
    lease = validate_runtime_credential_lease_reference(
        lease_request, request.credential_lease_reference
    )
    invocation = request.invocation
    envelope = invocation.envelope
    identity = envelope.effect_identity
    attempt = invocation.attempt
    scope = lease_request.scope

    if lease_request.adapter_family is not RuntimeAdapterFamily.CONNECTOR:
        raise RuntimePortCredentialError("connector materialization requires connector family")
    expected = (
        envelope.adapter_family,
        envelope.adapter_reference,
        envelope.adapter_contract_version,
        identity.destination_reference,
        envelope.runtime_effect_delivery_envelope_id,
        envelope.envelope_digest_reference,
        identity.runtime_effect_id,
        identity.effect_idempotency_key,
        attempt.permit_reference_ids,
        identity.runtime_execution_request_id,
        attempt.runtime_effect_delivery_attempt_id,
        envelope.actor_id,
        envelope.agent_instance_id,
        identity.tenant_id,
        identity.organization_id,
        identity.classification,
    )
    actual = (
        lease_request.adapter_family,
        lease_request.adapter_reference,
        lease_request.adapter_contract_version,
        lease_request.destination_reference,
        lease_request.runtime_effect_delivery_envelope_id,
        lease_request.envelope_digest_reference,
        lease_request.runtime_effect_id,
        lease_request.effect_idempotency_key,
        lease_request.permit_reference_ids,
        scope.runtime_execution_request_id,
        scope.attempt_id,
        scope.actor_id,
        scope.agent_instance_id,
        scope.tenant_id,
        scope.organization_id,
        scope.classification,
    )
    if actual != expected:
        raise RuntimePortCredentialError("connector materialization binding differs")
    if request.requested_at < lease.issued_at or request.requested_at >= lease.expires_at:
        raise RuntimePortCredentialError("connector materialization lease is not active")
    if request.requested_at >= attempt.deadline:
        raise RuntimePortCredentialError("connector materialization attempt is expired")
    return request


def validate_runtime_connector_delivery_result(
    request: RuntimeConnectorMaterializationRequest,
    result: RuntimeEffectDeliveryResult,
) -> RuntimeEffectDeliveryResult:
    validate_runtime_connector_materialization_request(request)
    validate_runtime_effect_delivery_result(
        request.invocation.envelope,
        request.invocation.attempt,
        result,
    )
    if result.certainty is RuntimeEffectDeliveryCertainty.DELIVERED and (
        result.acknowledgement_reference is None or result.acknowledgement_digest_reference is None
    ):
        raise RuntimePortContractError("delivered connector result lacks acknowledgement")
    if (
        result.certainty is RuntimeEffectDeliveryCertainty.DEFINITELY_NOT_DELIVERED
        and result.acknowledgement_reference is not None
    ):
        raise RuntimePortContractError("definite non-delivery contains acknowledgement")
    return result


def validate_runtime_connector_observation_invocation(
    invocation: RuntimeConnectorObservationInvocation,
) -> RuntimeConnectorObservationInvocation:
    envelope = invocation.envelope
    identity = envelope.effect_identity
    result = invocation.ambiguous_result
    request = invocation.reconciliation_request
    if result.certainty is not RuntimeEffectDeliveryCertainty.AMBIGUOUS:
        raise RuntimePortReconciliationError("connector observation requires ambiguous result")
    expected = (
        identity.runtime_effect_id,
        result.runtime_effect_delivery_result_id,
        identity.tenant_id,
        identity.organization_id,
        identity.destination_reference,
        identity.effect_idempotency_key,
        identity.root_lineage_id,
        identity.root_lineage_digest_reference,
        result.acknowledgement_reference,
        result.acknowledgement_digest_reference,
        identity.classification,
    )
    actual = (
        request.runtime_effect_id,
        request.ambiguous_result_id,
        request.tenant_id,
        request.organization_id,
        request.destination_reference,
        request.effect_idempotency_key,
        request.root_lineage_id,
        request.root_lineage_digest_reference,
        request.acknowledgement_reference,
        request.acknowledgement_digest_reference,
        request.classification,
    )
    if actual != expected:
        raise RuntimePortReconciliationError("connector observation binding differs")
    if invocation.requested_at < result.completed_at:
        raise RuntimePortReconciliationError("connector observation predates delivery result")
    return invocation


def validate_runtime_connector_observation_materialization_request(
    request: RuntimeConnectorObservationMaterializationRequest,
) -> RuntimeConnectorObservationMaterializationRequest:
    invocation = validate_runtime_connector_observation_invocation(request.invocation)
    lease_request = request.credential_lease_request
    lease = validate_runtime_credential_lease_reference(
        lease_request, request.credential_lease_reference
    )
    envelope = invocation.envelope
    identity = envelope.effect_identity
    reconciliation = invocation.reconciliation_request
    scope = lease_request.scope

    if lease_request.adapter_family is not RuntimeAdapterFamily.CONNECTOR:
        raise RuntimePortCredentialError("connector observation requires connector family")
    expected = (
        request.connector_provisioning_reference,
        request.connector_provisioning_reference,
        envelope.adapter_reference,
        envelope.adapter_contract_version,
        identity.destination_reference,
        envelope.runtime_effect_delivery_envelope_id,
        envelope.envelope_digest_reference,
        identity.runtime_effect_id,
        identity.effect_idempotency_key,
        reconciliation.permit_reference_ids,
        identity.runtime_execution_request_id,
        reconciliation.ambiguous_attempt_id,
        envelope.actor_id,
        envelope.agent_instance_id,
        identity.tenant_id,
        identity.organization_id,
        identity.classification,
        identity.root_lineage_id,
        identity.root_lineage_digest_reference,
        reconciliation.runtime_authority_bundle_id,
        reconciliation.runtime_admission_decision_id,
    )
    actual = (
        lease_request.connector_provisioning_reference,
        lease.connector_provisioning_reference,
        lease_request.adapter_reference,
        lease_request.adapter_contract_version,
        lease_request.destination_reference,
        lease_request.runtime_effect_delivery_envelope_id,
        lease_request.envelope_digest_reference,
        lease_request.runtime_effect_id,
        lease_request.effect_idempotency_key,
        lease_request.permit_reference_ids,
        scope.runtime_execution_request_id,
        scope.attempt_id,
        scope.actor_id,
        scope.agent_instance_id,
        scope.tenant_id,
        scope.organization_id,
        scope.classification,
        scope.root_lineage_id,
        scope.root_lineage_digest_reference,
        scope.runtime_authority_bundle_id,
        scope.runtime_admission_decision_id,
    )
    if actual != expected:
        raise RuntimePortCredentialError("connector observation materialization binding differs")
    if request.connector_provisioning_reference != reconciliation.connector_provisioning_reference:
        raise RuntimePortCredentialError("connector observation provisioning differs")
    if lease_request.requested_at != request.requested_at:
        raise RuntimePortCredentialError("connector observation lease request time differs")
    if request.requested_at < reconciliation.requested_at:
        raise RuntimePortCredentialError("connector observation predates reconciliation request")
    if request.requested_at < lease.issued_at or request.requested_at >= lease.expires_at:
        raise RuntimePortCredentialError("connector observation lease is not active")
    return request


def validate_runtime_connector_observation(
    request: RuntimeConnectorObservationMaterializationRequest,
    observation: RuntimeEffectReconciliationObservation,
) -> RuntimeEffectReconciliationObservation:
    validate_runtime_connector_observation_materialization_request(request)
    invocation = request.invocation
    validate_runtime_effect_reconciliation(
        invocation.reconciliation_request,
        observation,
    )
    if observation.observed_at < invocation.requested_at:
        raise RuntimePortReconciliationError("connector observation predates invocation")
    return observation
