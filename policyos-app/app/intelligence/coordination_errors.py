"""Safe errors for Secretary coordination preparation."""


class CoordinationError(ValueError):
    code = "coordination_error"


class CoordinationRequestError(CoordinationError):
    code = "coordination_request_error"


class CoordinationContextError(CoordinationError):
    code = "coordination_context_error"


class CoordinationIdentityError(CoordinationError):
    code = "coordination_identity_error"


class CoordinationClassificationError(CoordinationError):
    code = "coordination_classification_error"


class CoordinationDagError(CoordinationError):
    code = "coordination_dag_error"
