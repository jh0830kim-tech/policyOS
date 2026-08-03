"""Deterministic zero-side-effect dry-run runtime adapter."""

from app.runtime.adapters._base import _DeterministicRuntimeAdapter
from app.runtime.adapters.validation import validate_runtime_dry_run_envelope
from app.runtime.ports import RuntimeAdapterInvocationEnvelope


class DryRunRuntimeAdapter(_DeterministicRuntimeAdapter):
    """Accept only an exact governed dry-run envelope and supplied result."""

    def _validate_mode(
        self, envelope: RuntimeAdapterInvocationEnvelope
    ) -> RuntimeAdapterInvocationEnvelope:
        return validate_runtime_dry_run_envelope(envelope)
