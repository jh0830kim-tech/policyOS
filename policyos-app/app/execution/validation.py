"""Bounded JSON and deterministic graph validation for execution contracts."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol

from app.ai.privacy import DataClassification
from app.execution.errors import (
    CyclicExecutionPlanError,
    ExecutionClassificationError,
    InvalidStepDependencyError,
)

MAX_COLLECTION_ITEMS = 100
MAX_METADATA_BYTES = 16_000
MAX_OUTPUT_BYTES = 1_000_000
MAX_NESTING = 5
MAX_PLAN_STEPS = 500
MAX_DEPENDENCIES = 100

_SAFE_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_SECRET_KEY = re.compile(
    r"(?i)(authorization|cookie|credential|password|passwd|secret|token|api.?key|private.?key)"
)
_SECRET_VALUE = re.compile(r"(?i)(bearer\s+\S+|sk-[A-Za-z0-9_-]{12,})")
_CLASSIFICATION_RANK = {
    DataClassification.PUBLIC: 0,
    DataClassification.INTERNAL: 1,
    DataClassification.CONFIDENTIAL: 2,
    DataClassification.RESTRICTED: 3,
}


class StepLike(Protocol):
    step_id: str
    sequence: int
    dependencies: tuple[str, ...]


def require_aware(value: datetime | None, field: str) -> datetime | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError(f"{field} must be timezone-aware")
    return value


def require_not_lower(
    child: DataClassification, parent: DataClassification, *, field: str = "classification"
) -> None:
    if _CLASSIFICATION_RANK[child] < _CLASSIFICATION_RANK[parent]:
        raise ExecutionClassificationError(f"{field} cannot be lower than its trusted context")


def validate_json(
    value: Any,
    *,
    max_bytes: int = MAX_METADATA_BYTES,
    field: str = "metadata",
    depth: int = 0,
) -> Any:
    """Reject unsafe/unbounded values without stringifying arbitrary objects."""
    if depth > MAX_NESTING:
        raise ValueError(f"{field} nesting exceeds limit")
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if len(value.encode("utf-8")) > max_bytes:
            raise ValueError(f"{field} exceeds size limit")
        if _SECRET_VALUE.search(value):
            raise ValueError(f"{field} contains secret-like content")
        return value
    if isinstance(value, Mapping):
        if len(value) > MAX_COLLECTION_ITEMS:
            raise ValueError(f"{field} collection exceeds limit")
        for key, nested in value.items():
            if not isinstance(key, str) or not _SAFE_KEY.fullmatch(key):
                raise ValueError(f"{field} contains an invalid key")
            if _SECRET_KEY.search(key):
                raise ValueError(f"{field} contains a secret-like key")
            validate_json(nested, max_bytes=max_bytes, field=field, depth=depth + 1)
    elif isinstance(value, (list, tuple)):
        if len(value) > MAX_COLLECTION_ITEMS:
            raise ValueError(f"{field} collection exceeds limit")
        for nested in value:
            validate_json(nested, max_bytes=max_bytes, field=field, depth=depth + 1)
    else:
        raise ValueError(f"{field} must contain JSON-compatible values")
    if len(_json_size(value)) > max_bytes:
        raise ValueError(f"{field} exceeds size limit")
    return value


def _json_size(value: Any) -> bytes:
    import json

    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def validate_dependency_graph(steps: Sequence[StepLike]) -> None:
    if not steps:
        raise InvalidStepDependencyError("Execution plan requires at least one step")
    if len(steps) > MAX_PLAN_STEPS:
        raise InvalidStepDependencyError("Execution plan exceeds step limit")
    ids = [step.step_id for step in steps]
    if len(ids) != len(set(ids)):
        raise InvalidStepDependencyError("Execution plan contains duplicate step IDs")
    known = set(ids)
    for step in steps:
        if len(step.dependencies) > MAX_DEPENDENCIES:
            raise InvalidStepDependencyError("Step exceeds dependency limit")
        if len(step.dependencies) != len(set(step.dependencies)):
            raise InvalidStepDependencyError("Step contains duplicate dependencies")
        if step.step_id in step.dependencies:
            raise InvalidStepDependencyError("Step cannot depend on itself")
        if not set(step.dependencies) <= known:
            raise InvalidStepDependencyError("Step references an unknown dependency")
    topological_step_ids(steps)


def topological_step_ids(steps: Sequence[StepLike]) -> tuple[str, ...]:
    """Return an O(V+E) topological order using (sequence, step_id) ties."""
    by_id = {step.step_id: step for step in steps}
    indegree = {step.step_id: len(step.dependencies) for step in steps}
    children: dict[str, list[str]] = defaultdict(list)
    for step in steps:
        for dependency in step.dependencies:
            children[dependency].append(step.step_id)
    ready = sorted(
        (by_id[step_id].sequence, step_id) for step_id, degree in indegree.items() if degree == 0
    )
    ordered: list[str] = []
    while ready:
        _, step_id = ready.pop(0)
        ordered.append(step_id)
        for child in sorted(children[step_id], key=lambda item: (by_id[item].sequence, item)):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append((by_id[child].sequence, child))
                ready.sort()
    if len(ordered) != len(steps):
        raise CyclicExecutionPlanError("Execution plan contains a dependency cycle")
    return tuple(ordered)
