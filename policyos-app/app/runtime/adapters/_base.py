"""Shared immutable implementation for per-invocation deterministic adapters."""

from dataclasses import dataclass

from app.runtime.adapters.validation import (
    validate_runtime_adapter_exact_envelope,
    validate_runtime_adapter_supplied_result,
)
from app.runtime.ports import (
    RuntimeAdapterFamily,
    RuntimeAdapterInvocationEnvelope,
    RuntimeAdapterInvocationResult,
)


@dataclass(frozen=True, slots=True)
class _DeterministicRuntimeAdapter:
    """Bind one adapter instance to one complete immutable invocation."""

    expected_envelope: RuntimeAdapterInvocationEnvelope
    supplied_result: RuntimeAdapterInvocationResult

    def __post_init__(self) -> None:
        self._validate_mode(self.expected_envelope)
        validate_runtime_adapter_supplied_result(
            self.expected_envelope, self.supplied_result
        )

    @property
    def adapter_reference(self) -> str:
        return self.expected_envelope.adapter_reference

    @property
    def adapter_contract_version(self) -> str:
        return self.expected_envelope.adapter_contract_version

    @property
    def adapter_family(self) -> RuntimeAdapterFamily:
        return self.expected_envelope.adapter_family

    async def invoke(
        self, envelope: RuntimeAdapterInvocationEnvelope
    ) -> RuntimeAdapterInvocationResult:
        validated = validate_runtime_adapter_exact_envelope(
            self.expected_envelope, envelope
        )
        self._validate_mode(validated)
        return validate_runtime_adapter_supplied_result(validated, self.supplied_result)

    def _validate_mode(
        self, envelope: RuntimeAdapterInvocationEnvelope
    ) -> RuntimeAdapterInvocationEnvelope:
        return envelope
