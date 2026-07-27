"""Stable, payload-safe Secretary integration approval errors."""

from app.execution.errors import ExecutionDomainError


class ApprovalError(ExecutionDomainError):
    code = "secretary_integration_approval_error"


class ApprovalValidationError(ApprovalError):
    code = "secretary_integration_approval_validation"


class ApprovalEligibilityError(ApprovalValidationError):
    code = "secretary_integration_approval_eligibility"


class ApprovalAuthorizationError(ApprovalValidationError):
    code = "secretary_integration_approval_authorization"


class ApprovalActorError(ApprovalAuthorizationError):
    code = "secretary_integration_approval_actor"


class ApprovalSeparationOfDutiesError(ApprovalAuthorizationError):
    code = "secretary_integration_approval_separation"


class ApprovalIdentityMismatchError(ApprovalValidationError):
    code = "secretary_integration_approval_identity_mismatch"


class ApprovalTenantMismatchError(ApprovalIdentityMismatchError):
    code = "secretary_integration_approval_tenant_mismatch"


class ApprovalClassificationMismatchError(ApprovalIdentityMismatchError):
    code = "secretary_integration_approval_classification_mismatch"


class ApprovalDecisionError(ApprovalValidationError):
    code = "secretary_integration_approval_decision"


class ApprovalTimestampError(ApprovalValidationError):
    code = "secretary_integration_approval_timestamp"


class ApprovalDuplicateError(ApprovalValidationError):
    code = "secretary_integration_approval_duplicate"


class ApprovalAcknowledgementError(ApprovalValidationError):
    code = "secretary_integration_approval_acknowledgement"
