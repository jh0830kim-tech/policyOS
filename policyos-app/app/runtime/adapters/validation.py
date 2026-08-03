"""Pure fail-closed validation for deterministic runtime adapters."""

from app.runtime.adapters.errors import (
    RuntimeAdapterBindingError,
    RuntimeAdapterModeError,
    RuntimeAdapterResultError,
)
from app.runtime.authority import RuntimeExecutionEnvironment
from app.runtime.planning import ExecutionPlanMode
from app.runtime.ports import (
    RuntimeAdapterInvocationEnvelope,
    RuntimeAdapterInvocationResult,
    validate_runtime_adapter_invocation_result,
)


def validate_runtime_adapter_exact_envelope(
    expected: RuntimeAdapterInvocationEnvelope,
    actual: RuntimeAdapterInvocationEnvelope,
) -> RuntimeAdapterInvocationEnvelope:
    """Reject every invocation fact substituted after adapter selection."""

    if actual != expected:
        raise RuntimeAdapterBindingError(
            "runtime adapter invocation differs from its exact immutable binding"
        )
    return actual


def validate_runtime_adapter_supplied_result(
    envelope: RuntimeAdapterInvocationEnvelope,
    result: RuntimeAdapterInvocationResult,
) -> RuntimeAdapterInvocationResult:
    """Validate a caller-supplied result without creating result facts."""

    try:
        return validate_runtime_adapter_invocation_result(result, envelope)
    except ValueError as exc:
        raise RuntimeAdapterResultError(
            "runtime adapter result differs from its invocation"
        ) from exc


def validate_runtime_dry_run_envelope(
    envelope: RuntimeAdapterInvocationEnvelope,
) -> RuntimeAdapterInvocationEnvelope:
    """Require both governed mode selectors to identify a dry run."""

    binding = envelope.policy_binding
    if binding.plan_mode is not ExecutionPlanMode.DRY_RUN or (
        binding.execution_environment is not RuntimeExecutionEnvironment.DRY_RUN
    ):
        raise RuntimeAdapterModeError(
            "dry-run adapter requires exact dry-run plan and execution modes"
        )
    return envelope
