"""Strict allowlisted serialization for CP9 Registry persistence."""

import json
from enum import StrEnum

from pydantic import BaseModel, ValidationError

from app.runtime.persistence.errors import RuntimePersistenceSerializationError
from app.runtime.ports import RuntimeEffectReconciliationRequest
from app.runtime.registry import (
    RuntimeActionRegistrySnapshot,
    RuntimeActionResolutionDecision,
    RuntimeActionResolutionRequest,
    RuntimeRegistrySnapshotEntry,
    validate_runtime_action_resolution_decision,
    validate_runtime_registry_snapshot,
)


class RuntimeRegistryPayloadType(StrEnum):
    SNAPSHOT = "snapshot"
    ENTRY = "entry"
    RESOLUTION_REQUEST = "resolution_request"
    RESOLUTION_DECISION = "resolution_decision"
    RECONCILIATION_REQUEST = "reconciliation_request"


type RuntimeRegistryPayload = (
    RuntimeActionRegistrySnapshot
    | RuntimeRegistrySnapshotEntry
    | RuntimeActionResolutionRequest
    | RuntimeActionResolutionDecision
    | RuntimeEffectReconciliationRequest
)

_MODEL_BY_TYPE: dict[RuntimeRegistryPayloadType, type[BaseModel]] = {
    RuntimeRegistryPayloadType.SNAPSHOT: RuntimeActionRegistrySnapshot,
    RuntimeRegistryPayloadType.ENTRY: RuntimeRegistrySnapshotEntry,
    RuntimeRegistryPayloadType.RESOLUTION_REQUEST: RuntimeActionResolutionRequest,
    RuntimeRegistryPayloadType.RESOLUTION_DECISION: RuntimeActionResolutionDecision,
    RuntimeRegistryPayloadType.RECONCILIATION_REQUEST: RuntimeEffectReconciliationRequest,
}


def serialize_registry_payload(payload: RuntimeRegistryPayload) -> dict[str, object]:
    if type(payload) not in _MODEL_BY_TYPE.values():
        raise RuntimePersistenceSerializationError("Registry payload type is not allowlisted")
    return payload.model_dump(mode="json")


def deserialize_registry_payload(
    payload_type: RuntimeRegistryPayloadType,
    payload: dict[str, object],
) -> RuntimeRegistryPayload:
    model = _MODEL_BY_TYPE.get(payload_type)
    if model is None:
        raise RuntimePersistenceSerializationError("Registry payload type is not allowlisted")
    try:
        value = model.model_validate_json(json.dumps(payload, separators=(",", ":")))
    except (TypeError, ValueError, ValidationError) as exc:
        raise RuntimePersistenceSerializationError(
            "stored Registry payload failed strict allowlisted validation"
        ) from exc
    return value  # type: ignore[return-value]


def validate_registry_graph(
    snapshot: RuntimeActionRegistrySnapshot,
    request: RuntimeActionResolutionRequest,
    decision: RuntimeActionResolutionDecision,
) -> None:
    validate_runtime_registry_snapshot(snapshot)
    validate_runtime_action_resolution_decision(decision, request, snapshot)


__all__ = (
    "RuntimeRegistryPayload",
    "RuntimeRegistryPayloadType",
    "deserialize_registry_payload",
    "serialize_registry_payload",
    "validate_registry_graph",
)
