"""Strict allowlisted serialization for CP9 logical execution results."""

import json

from pydantic import ValidationError

from app.runtime.persistence.errors import RuntimePersistenceSerializationError
from app.runtime.ports import RuntimeApiLogicalExecutionResult


def serialize_logical_execution_result(
    result: RuntimeApiLogicalExecutionResult,
) -> dict[str, object]:
    if not isinstance(result, RuntimeApiLogicalExecutionResult):
        raise RuntimePersistenceSerializationError(
            "logical execution-result type is not allowlisted"
        )
    return result.model_dump(mode="json")


def deserialize_logical_execution_result(
    payload: dict[str, object],
) -> RuntimeApiLogicalExecutionResult:
    try:
        return RuntimeApiLogicalExecutionResult.model_validate_json(
            json.dumps(payload, separators=(",", ":"))
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise RuntimePersistenceSerializationError(
            "stored logical execution-result failed strict validation"
        ) from exc


__all__ = (
    "deserialize_logical_execution_result",
    "serialize_logical_execution_result",
)
