"""Stable, payload-safe provider executor errors."""

from app.execution.errors import ExecutionDomainError


class ProviderExecutorError(ExecutionDomainError):
    code = "provider_executor_error"


class ExecutorIdentityMismatchError(ProviderExecutorError):
    code = "executor_identity_mismatch"


class ExecutorClassificationError(ProviderExecutorError):
    code = "executor_classification_error"


class ExecutorRevisionConflictError(ProviderExecutorError):
    code = "executor_revision_conflict"


class ExecutorStepStateError(ProviderExecutorError):
    code = "executor_step_state_error"


class ExecutorCancellationError(ProviderExecutorError):
    code = "executor_cancellation"


class ExecutorDeadlineExceededError(ProviderExecutorError):
    code = "executor_deadline_exceeded"


class ProviderAdapterCatalogError(ProviderExecutorError):
    code = "provider_adapter_catalog_error"


class DuplicateProviderAdapterError(ProviderAdapterCatalogError):
    code = "duplicate_provider_adapter"


class UnknownProviderAdapterError(ProviderAdapterCatalogError):
    code = "unknown_provider_adapter"


class ProviderAdapterCapabilityError(ProviderAdapterCatalogError):
    code = "provider_adapter_capability"


class ProviderInvocationError(ProviderExecutorError):
    code = "provider_invocation_error"


class ProviderOutputError(ProviderExecutorError):
    code = "provider_output_error"


class ProviderResultMismatchError(ProviderOutputError):
    code = "provider_result_mismatch"
