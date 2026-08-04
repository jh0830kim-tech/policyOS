"""Strict allowlisted JSON serialization for CP8 delivery persistence."""

import json

from pydantic import BaseModel, ValidationError

from app.runtime.persistence.errors import RuntimePersistenceSerializationError
from app.runtime.ports import (
    RuntimeEffectClaim,
    RuntimeEffectClaimRequest,
    RuntimeEffectDeadLetterRecord,
    RuntimeEffectDefinitelyNotInvoked,
    RuntimeEffectDeliveryAttempt,
    RuntimeEffectDeliveryEnvelope,
    RuntimeEffectDeliveryResult,
    RuntimeEffectLifecycleAppendRequest,
    RuntimeEffectLifecycleReceiptFact,
    RuntimeEffectLifecycleRecord,
    RuntimeEffectReceiptFact,
    RuntimeEffectReconciliationObservation,
    RuntimeEffectRetryDecision,
    RuntimeInitialEffectEnqueue,
)

_ALLOWED_MODELS = (
    RuntimeEffectClaim,
    RuntimeEffectClaimRequest,
    RuntimeEffectDeadLetterRecord,
    RuntimeEffectDefinitelyNotInvoked,
    RuntimeEffectDeliveryAttempt,
    RuntimeEffectDeliveryEnvelope,
    RuntimeEffectDeliveryResult,
    RuntimeEffectLifecycleAppendRequest,
    RuntimeEffectLifecycleRecord,
    RuntimeEffectLifecycleReceiptFact,
    RuntimeEffectReceiptFact,
    RuntimeEffectReconciliationObservation,
    RuntimeEffectRetryDecision,
    RuntimeInitialEffectEnqueue,
)


def serialize_delivery_model(value: BaseModel) -> dict[str, object]:
    if type(value) not in _ALLOWED_MODELS:
        raise RuntimePersistenceSerializationError(
            "delivery model type is not allowlisted"
        )
    return value.model_dump(mode="json")


def deserialize_delivery_model[DeliveryModel: BaseModel](
    model: type[DeliveryModel], payload: dict[str, object]
) -> DeliveryModel:
    if model not in _ALLOWED_MODELS:
        raise RuntimePersistenceSerializationError(
            "delivery model type is not allowlisted"
        )
    try:
        return model.model_validate_json(json.dumps(payload, separators=(",", ":")))
    except (TypeError, ValueError, ValidationError) as exc:
        raise RuntimePersistenceSerializationError(
            "stored delivery model failed strict allowlisted validation"
        ) from exc


__all__ = ("deserialize_delivery_model", "serialize_delivery_model")
