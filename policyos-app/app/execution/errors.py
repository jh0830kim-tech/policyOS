"""Stable, content-safe execution domain errors."""


class ExecutionDomainError(ValueError):
    """Base error whose message never includes execution payloads."""


class InvalidExecutionRequestError(ExecutionDomainError):
    pass


class InvalidExecutionPlanError(ExecutionDomainError):
    pass


class InvalidStepDependencyError(InvalidExecutionPlanError):
    pass


class CyclicExecutionPlanError(InvalidExecutionPlanError):
    pass


class ExecutionClassificationError(ExecutionDomainError):
    pass
