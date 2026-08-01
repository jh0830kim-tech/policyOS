"""Internal deterministic classification helpers for evaluation contracts."""

from app.ai.privacy import DataClassification
from app.execution.validation import require_not_lower


def effective_classification(*classifications: DataClassification) -> DataClassification:
    """Return the most restrictive explicit classification, failing on empty input."""
    if not classifications:
        raise ValueError("at least one explicit classification is required")
    ordering = tuple(DataClassification)
    return max(classifications, key=ordering.index)


def require_classification_not_lower(
    classification: DataClassification,
    *sources: DataClassification,
    field: str,
) -> None:
    """Require a classification to dominate every explicitly supplied source."""
    if not sources:
        raise ValueError("at least one source classification is required")
    for source in sources:
        require_not_lower(classification, source, field=field)
