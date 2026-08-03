"""Deterministic zero-I/O fake runtime adapter."""

from app.runtime.adapters._base import _DeterministicRuntimeAdapter


class FakeRuntimeAdapter(_DeterministicRuntimeAdapter):
    """Return one exact caller-supplied result without external effects."""
