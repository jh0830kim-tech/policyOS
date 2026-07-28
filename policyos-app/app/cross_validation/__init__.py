"""Intentional public API for independent cross-validation run contracts."""

from app.cross_validation.audit import (
    CrossValidationAuditEvent,
    CrossValidationAuditRecord,
    create_collection_audit_record,
    create_plan_audit_record,
    create_run_binding_audit_record,
    create_run_result_audit_record,
)
from app.cross_validation.collection import (
    bind_model_run_result,
    create_run_collection,
)
from app.cross_validation.domain import (
    AuthorizedModelRun,
    CrossValidationPlan,
    CrossValidationRunCollection,
    ModelRunResult,
    ModelRunRole,
    ModelRunStatus,
    PlannedModelRun,
    RunCollectionStatus,
    ValidationStrategy,
)
from app.cross_validation.errors import (
    CrossValidationAuthorizationMismatchError,
    CrossValidationCollectionError,
    CrossValidationError,
    CrossValidationPermitMismatchError,
    CrossValidationPlanError,
    CrossValidationPlanMismatchError,
    CrossValidationResultMismatchError,
    CrossValidationRunDuplicateError,
    CrossValidationValidationError,
)
from app.cross_validation.planning import (
    bind_authorized_model_run,
    validate_cross_validation_plan,
)

__all__ = (
    "AuthorizedModelRun",
    "CrossValidationAuditEvent",
    "CrossValidationAuditRecord",
    "CrossValidationAuthorizationMismatchError",
    "CrossValidationCollectionError",
    "CrossValidationError",
    "CrossValidationPermitMismatchError",
    "CrossValidationPlan",
    "CrossValidationPlanError",
    "CrossValidationPlanMismatchError",
    "CrossValidationResultMismatchError",
    "CrossValidationRunCollection",
    "CrossValidationRunDuplicateError",
    "CrossValidationValidationError",
    "ModelRunResult",
    "ModelRunRole",
    "ModelRunStatus",
    "PlannedModelRun",
    "RunCollectionStatus",
    "ValidationStrategy",
    "bind_authorized_model_run",
    "bind_model_run_result",
    "create_collection_audit_record",
    "create_plan_audit_record",
    "create_run_binding_audit_record",
    "create_run_collection",
    "create_run_result_audit_record",
    "validate_cross_validation_plan",
)
