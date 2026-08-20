"""Pure exact-binding validation for managed connector contracts."""

import hashlib
import json
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import ValidationError

from app.runtime.ports.connector import (
    RUNTIME_CONNECTOR_REQUEST_BODY_MAX_BYTES,
    RUNTIME_CONNECTOR_RESPONSE_BODY_MAX_BYTES,
    RuntimeConnectorDeliveryAcknowledgement,
    RuntimeConnectorDeliveryMaterializationFacts,
    RuntimeConnectorDeliveryObservation,
    RuntimeConnectorDeliveryWireRequest,
    RuntimeConnectorDeliveryWireResponse,
    RuntimeConnectorMaterializationRequest,
    RuntimeConnectorObservationInvocation,
    RuntimeConnectorObservationMaterializationFacts,
    RuntimeConnectorObservationMaterializationRequest,
    RuntimeConnectorObservationWireRequest,
    RuntimeConnectorObservationWireResponse,
    RuntimeConnectorProvisioningCatalog,
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


def _canonical_datetime(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
        raise RuntimePortContractError("connector canonical datetime must already be UTC")
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _canonical_scalar(value: object) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bool):
        raise RuntimePortContractError("connector canonical value cannot be boolean")
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, UUID):
        return str(value).encode("utf-8")
    if isinstance(value, datetime):
        return _canonical_datetime(value).encode("utf-8")
    if isinstance(value, int):
        return str(value).encode("ascii")
    if isinstance(value, str):
        if not value:
            raise RuntimePortContractError("connector canonical string cannot be empty")
        return value.encode("utf-8")
    raise RuntimePortContractError("unsupported connector canonical value")


def _component(value: object) -> bytes:
    raw = _canonical_scalar(value)
    return str(len(raw)).encode("ascii") + b":" + raw


def runtime_connector_canonical_digest(values: tuple[object, ...]) -> str:
    encoded = bytearray()
    for value in values:
        if isinstance(value, tuple):
            encoded.extend(_component(len(value)))
            for item in value:
                encoded.extend(_component(item))
        else:
            encoded.extend(_component(value))
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _delivery_request_projection(
    request: RuntimeConnectorDeliveryWireRequest,
) -> tuple[object, ...]:
    return tuple(getattr(request, name) for name in type(request).model_fields)


def _delivery_acknowledgement_projection(
    acknowledgement: RuntimeConnectorDeliveryAcknowledgement,
) -> tuple[object, ...]:
    return tuple(
        getattr(acknowledgement, name) for name in tuple(type(acknowledgement).model_fields)[:-1]
    )


def _observation_request_projection(
    request: RuntimeConnectorObservationWireRequest,
) -> tuple[object, ...]:
    return tuple(getattr(request, name) for name in type(request).model_fields)


def _observation_projection(
    observation: RuntimeConnectorDeliveryObservation,
) -> tuple[object, ...]:
    return tuple(getattr(observation, name) for name in tuple(type(observation).model_fields)[:-1])


def validate_runtime_connector_delivery_wire_request(
    source: RuntimeConnectorMaterializationRequest,
    request: RuntimeConnectorDeliveryWireRequest,
) -> RuntimeConnectorDeliveryWireRequest:
    validate_runtime_connector_materialization_request(source)
    invocation = source.invocation
    envelope = invocation.envelope
    identity = envelope.effect_identity
    expected = (
        identity.runtime_effect_id,
        identity.runtime_execution_request_id,
        invocation.attempt.runtime_effect_delivery_attempt_id,
        invocation.runtime_effect_delivery_invocation_id,
        envelope.runtime_effect_delivery_envelope_id,
        identity.payload_reference,
        identity.payload_digest_reference,
        identity.destination_reference,
        source.credential_lease_request.connector_provisioning_reference,
        envelope.adapter_reference,
        envelope.adapter_contract_version,
        identity.effect_idempotency_key,
        identity.tenant_id,
        identity.organization_id,
        identity.classification,
        identity.root_lineage_id,
        identity.root_lineage_digest_reference,
        invocation.attempt.permit_reference_ids,
    )
    actual = tuple(_delivery_request_projection(request)[2:])
    if actual != expected:
        raise RuntimePortContractError("connector delivery wire request binding differs")
    runtime_connector_canonical_digest(_delivery_request_projection(request))
    return request


def validate_runtime_connector_delivery_acknowledgement(
    request: RuntimeConnectorDeliveryWireRequest,
    response: RuntimeConnectorDeliveryWireResponse,
    *,
    http_status: int,
    trusted_started_at: datetime,
    trusted_completed_at: datetime,
) -> RuntimeConnectorDeliveryAcknowledgement:
    acknowledgement = response.delivery_acknowledgement
    if http_status != 200:
        raise RuntimePortContractError("connector acknowledgement requires exact HTTP 200")
    expected = (
        request.runtime_effect_id,
        request.runtime_effect_delivery_attempt_id,
        request.destination_reference,
        request.effect_idempotency_key,
    )
    actual = (
        acknowledgement.runtime_effect_id,
        acknowledgement.runtime_effect_delivery_attempt_id,
        acknowledgement.destination_reference,
        acknowledgement.effect_idempotency_key,
    )
    if actual != expected:
        raise RuntimePortContractError("connector acknowledgement identity differs")
    if not (trusted_started_at <= acknowledgement.accepted_at <= trusted_completed_at):
        raise RuntimePortContractError("connector acknowledgement time is outside trusted window")
    digest = runtime_connector_canonical_digest(
        _delivery_acknowledgement_projection(acknowledgement)
    )
    if acknowledgement.acknowledgement_digest_reference != digest:
        raise RuntimePortContractError("connector acknowledgement digest differs")
    return acknowledgement


def validate_runtime_connector_observation_wire_request(
    source: RuntimeConnectorObservationMaterializationRequest,
    request: RuntimeConnectorObservationWireRequest,
) -> RuntimeConnectorObservationWireRequest:
    validate_runtime_connector_observation_materialization_request(source)
    invocation = source.invocation
    envelope = invocation.envelope
    identity = envelope.effect_identity
    reconciliation = invocation.reconciliation_request
    expected = (
        invocation.runtime_connector_observation_invocation_id,
        identity.runtime_effect_id,
        reconciliation.ambiguous_attempt_id,
        reconciliation.acknowledgement_reference,
        reconciliation.acknowledgement_digest_reference,
        identity.destination_reference,
        source.connector_provisioning_reference,
        identity.effect_idempotency_key,
        identity.tenant_id,
        identity.organization_id,
        identity.classification,
        identity.root_lineage_id,
        identity.root_lineage_digest_reference,
        reconciliation.runtime_authority_bundle_id,
        reconciliation.runtime_admission_decision_id,
        reconciliation.permit_reference_ids,
        invocation.requested_at,
    )
    actual = tuple(_observation_request_projection(request)[2:])
    if actual != expected:
        raise RuntimePortContractError("connector observation wire request binding differs")
    runtime_connector_canonical_digest(_observation_request_projection(request))
    return request


def validate_runtime_connector_delivery_observation(
    request: RuntimeConnectorObservationWireRequest,
    response: RuntimeConnectorObservationWireResponse,
    *,
    http_status: int,
    trusted_completed_at: datetime,
) -> RuntimeConnectorDeliveryObservation:
    observation = response.delivery_observation
    if http_status != 200:
        raise RuntimePortContractError("connector observation requires exact HTTP 200")
    expected = (
        request.operation_reference,
        request.runtime_effect_id,
        request.runtime_effect_delivery_attempt_id,
        request.destination_reference,
        request.effect_idempotency_key,
    )
    actual = (
        observation.operation_reference,
        observation.runtime_effect_id,
        observation.runtime_effect_delivery_attempt_id,
        observation.destination_reference,
        observation.effect_idempotency_key,
    )
    if actual != expected or observation.observed_at > trusted_completed_at:
        raise RuntimePortContractError("connector observation binding differs")
    digest = runtime_connector_canonical_digest(_observation_projection(observation))
    if observation.observation_digest_reference != digest:
        raise RuntimePortContractError("connector observation digest differs")
    return observation


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RuntimePortContractError("connector JSON contains a duplicate field")
        result[key] = value
    return result


def _parse_closed_json(body: bytes, *, maximum_bytes: int) -> dict[str, Any]:
    if not body or len(body) > maximum_bytes or body.startswith(b"\xef\xbb\xbf"):
        raise RuntimePortContractError("connector JSON body is empty, BOM-prefixed, or oversized")
    try:
        text = body.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                RuntimePortContractError("connector JSON contains a non-finite number")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimePortContractError("connector JSON is malformed") from exc
    if not isinstance(value, dict):
        raise RuntimePortContractError("connector JSON top-level value must be an object")
    return value


def parse_runtime_connector_delivery_response(
    body: bytes,
) -> RuntimeConnectorDeliveryWireResponse:
    try:
        value = _parse_closed_json(body, maximum_bytes=RUNTIME_CONNECTOR_RESPONSE_BODY_MAX_BYTES)
        return RuntimeConnectorDeliveryWireResponse.model_validate_json(
            json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        )
    except ValidationError as exc:
        raise RuntimePortContractError("connector delivery response contract is invalid") from exc


def parse_runtime_connector_observation_response(
    body: bytes,
) -> RuntimeConnectorObservationWireResponse:
    try:
        value = _parse_closed_json(body, maximum_bytes=RUNTIME_CONNECTOR_RESPONSE_BODY_MAX_BYTES)
        return RuntimeConnectorObservationWireResponse.model_validate_json(
            json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        )
    except ValidationError as exc:
        raise RuntimePortContractError(
            "connector observation response contract is invalid"
        ) from exc


def encode_runtime_connector_wire_request(
    request: RuntimeConnectorDeliveryWireRequest | RuntimeConnectorObservationWireRequest,
) -> bytes:
    body = json.dumps(
        request.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(body) > RUNTIME_CONNECTOR_REQUEST_BODY_MAX_BYTES:
        raise RuntimePortContractError("connector request body exceeds the exact byte bound")
    return body


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


def validate_runtime_connector_delivery_materialization_facts(
    facts: RuntimeConnectorDeliveryMaterializationFacts,
    request: RuntimeConnectorMaterializationRequest,
) -> RuntimeConnectorDeliveryMaterializationFacts:
    lease_request = request.credential_lease_request
    expected = (
        request.runtime_connector_materialization_request_id,
        lease_request.runtime_credential_lease_request_id,
        lease_request.connector_provisioning_reference,
        lease_request.credential_reference,
        lease_request.credential_purpose_reference,
        request.requested_at,
        lease_request.expires_at,
    )
    actual = (
        facts.runtime_connector_materialization_request_id,
        facts.runtime_credential_lease_request_id,
        facts.connector_provisioning_reference,
        facts.credential_reference,
        facts.credential_purpose_reference,
        facts.requested_at,
        facts.expires_at,
    )
    if actual != expected:
        raise RuntimePortCredentialError("connector delivery materialization facts differ")
    return facts


def validate_runtime_connector_observation_materialization_facts(
    facts: RuntimeConnectorObservationMaterializationFacts,
    request: RuntimeConnectorObservationMaterializationRequest,
) -> RuntimeConnectorObservationMaterializationFacts:
    lease_request = request.credential_lease_request
    expected = (
        request.runtime_connector_observation_materialization_request_id,
        lease_request.runtime_credential_lease_request_id,
        request.connector_provisioning_reference,
        lease_request.credential_reference,
        lease_request.credential_purpose_reference,
        request.requested_at,
        lease_request.expires_at,
    )
    actual = (
        facts.runtime_connector_observation_materialization_request_id,
        facts.runtime_credential_lease_request_id,
        facts.connector_provisioning_reference,
        facts.credential_reference,
        facts.credential_purpose_reference,
        facts.requested_at,
        facts.expires_at,
    )
    if actual != expected:
        raise RuntimePortCredentialError("connector observation materialization facts differ")
    return facts


def validate_runtime_connector_provisioning_catalog(
    catalog: RuntimeConnectorProvisioningCatalog,
) -> RuntimeConnectorProvisioningCatalog:
    if len(catalog.entries) != 1:
        raise RuntimePortContractError("connector provisioning catalog cardinality differs")
    entry = catalog.entries[0]
    parsed = urlsplit(entry.endpoint_uri)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.netloc != parsed.netloc.lower()
        or parsed.port not in (None, 443)
    ):
        raise RuntimePortContractError("connector provisioning endpoint is not canonical HTTPS")
    return catalog


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
