"""Implementation-neutral governed adapter invocation protocol."""

from typing import Protocol, runtime_checkable

from app.runtime.ports._base import BoundedId, BoundedVersion
from app.runtime.ports.domain import (
    RuntimeAdapterFamily,
    RuntimeAdapterInvocationEnvelope,
    RuntimeAdapterInvocationResult,
)


@runtime_checkable
class RuntimeAdapterPort(Protocol):
    @property
    def adapter_reference(self) -> BoundedId: ...

    @property
    def adapter_contract_version(self) -> BoundedVersion: ...

    @property
    def adapter_family(self) -> RuntimeAdapterFamily: ...

    async def invoke(
        self, envelope: RuntimeAdapterInvocationEnvelope
    ) -> RuntimeAdapterInvocationResult: ...
