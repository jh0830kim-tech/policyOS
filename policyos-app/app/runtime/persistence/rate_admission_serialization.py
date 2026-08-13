"""Strict allowlisted serialization for ADR-103 rate-admission records."""

import json

from pydantic import ValidationError

from app.runtime.persistence.errors import RuntimePersistenceSerializationError
from app.runtime.ports import (
    RuntimeRateAdmissionDecision,
    RuntimeRatePolicyProvisionCommand,
    RuntimeRatePolicyRevocationCommand,
)


def _deserialize(model_type, payload: dict[str, object]):
    try:
        return model_type.model_validate_json(json.dumps(payload, separators=(",", ":")))
    except (TypeError, ValueError, ValidationError) as exc:
        raise RuntimePersistenceSerializationError(
            "stored rate-admission payload failed strict validation"
        ) from exc


def serialize_rate_policy_provision(
    command: RuntimeRatePolicyProvisionCommand,
) -> dict[str, object]:
    if not isinstance(command, RuntimeRatePolicyProvisionCommand):
        raise RuntimePersistenceSerializationError("rate-policy provision type is not allowlisted")
    return command.model_dump(mode="json")


def deserialize_rate_policy_provision(
    payload: dict[str, object],
) -> RuntimeRatePolicyProvisionCommand:
    return _deserialize(RuntimeRatePolicyProvisionCommand, payload)


def serialize_rate_policy_revocation(
    command: RuntimeRatePolicyRevocationCommand,
) -> dict[str, object]:
    if not isinstance(command, RuntimeRatePolicyRevocationCommand):
        raise RuntimePersistenceSerializationError("rate-policy revocation type is not allowlisted")
    return command.model_dump(mode="json")


def deserialize_rate_policy_revocation(
    payload: dict[str, object],
) -> RuntimeRatePolicyRevocationCommand:
    return _deserialize(RuntimeRatePolicyRevocationCommand, payload)


def serialize_rate_admission_decision(
    decision: RuntimeRateAdmissionDecision,
) -> dict[str, object]:
    if not isinstance(decision, RuntimeRateAdmissionDecision):
        raise RuntimePersistenceSerializationError(
            "rate-admission decision type is not allowlisted"
        )
    return decision.model_dump(mode="json")


def deserialize_rate_admission_decision(
    payload: dict[str, object],
) -> RuntimeRateAdmissionDecision:
    return _deserialize(RuntimeRateAdmissionDecision, payload)


__all__ = (
    "deserialize_rate_admission_decision",
    "deserialize_rate_policy_provision",
    "deserialize_rate_policy_revocation",
    "serialize_rate_admission_decision",
    "serialize_rate_policy_provision",
    "serialize_rate_policy_revocation",
)
