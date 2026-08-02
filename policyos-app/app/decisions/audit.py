"""Validation for caller-supplied Decision package audit metadata."""

from app.decisions.domain import DecisionPackageAuditMetadata
from app.decisions.errors import DecisionPackageAuditMetadataError


def validate_decision_package_audit_metadata(
    metadata: DecisionPackageAuditMetadata,
) -> DecisionPackageAuditMetadata:
    if metadata.unresolved_review_count > metadata.review_requirement_count:
        raise DecisionPackageAuditMetadataError(
            "unresolved_review_count exceeds review_requirement_count"
        )

    if metadata.disposition_count > 1:
        raise DecisionPackageAuditMetadataError(
            "disposition_count exceeds package bound"
        )

    return metadata