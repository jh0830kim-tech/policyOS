"""Safe typed errors for selection authorization and invocation guards."""


class ModelSelectionError(ValueError):
    code = "model_selection_error"


class ModelSelectionValidationError(ModelSelectionError):
    code = "model_selection_validation"


class SelectionAuthorizationError(ModelSelectionError):
    code = "selection_authorization"


class SelectionPolicyDeniedError(SelectionAuthorizationError):
    code = "selection_policy_denied"


class SelectionApprovalRequiredError(SelectionAuthorizationError):
    code = "selection_approval_required"


class SelectionApprovalError(SelectionAuthorizationError):
    code = "selection_approval"


class SelectionApprovalMismatchError(SelectionApprovalError):
    code = "selection_approval_mismatch"


class SelectionApprovalExpiredError(SelectionApprovalError):
    code = "selection_approval_expired"


class InvocationAuthorizationError(ModelSelectionError):
    code = "invocation_authorization"


class InvocationPermitMismatchError(InvocationAuthorizationError):
    code = "invocation_permit_mismatch"


class InvocationNotAuthorizedError(InvocationAuthorizationError):
    code = "invocation_not_authorized"


class AuditContractError(ModelSelectionError):
    code = "selection_audit_contract"
