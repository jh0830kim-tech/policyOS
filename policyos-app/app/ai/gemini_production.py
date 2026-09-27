"""Private Gemini request composition; no ambient credential discovery."""

from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable
from uuid import UUID

from pydantic import SecretStr

from app.ai.composition import OfficeComposition, build_office_composition_from_gateway
from app.ai.model_gateway import ModelConfigurationError, ModelRequest, ModelResponse
from app.ai.privacy import (
    DataClassification,
    NullProviderAuditSink,
    ProviderAuditSink,
    ProviderTransmissionPolicy,
    RegexRedactor,
)
from app.ai.production import OfficeCompositionBlueprint
from app.ai.providers.gemini_interactions import GeminiInteractionsGateway


@runtime_checkable
class GeminiCredentialAccessor(Protocol):
    """Deployment capability; every open returns a fresh managed credential lease."""

    def open(self) -> AbstractAsyncContextManager[SecretStr]: ...


@dataclass(frozen=True, slots=True)
class GeminiRequestExecutionScopeFactory:
    blueprint: OfficeCompositionBlueprint
    credential_accessor: GeminiCredentialAccessor = field(repr=False)
    timeout_seconds: float = 30.0
    max_retries: int = 0
    retry_backoff_seconds: float = 0.5
    redaction_terms: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        b = self.blueprint
        if not isinstance(b, OfficeCompositionBlueprint) or b.provider != "gemini":
            raise ModelConfigurationError("Gemini blueprint is required")
        if (
            any(
                not isinstance(value, str)
                or not value
                or value != value.strip()
                or len(value) > 200
                for value in (b.logical_model_id, b.provider_model_name, b.provider_instance_id)
            )
            or not isinstance(b.registry_id, UUID)
            or type(b.registry_revision) is not int
            or b.registry_revision < 1
        ):
            raise ModelConfigurationError("Gemini blueprint identity is incomplete")
        if not isinstance(self.credential_accessor, GeminiCredentialAccessor) or not callable(
            self.credential_accessor.open
        ):
            raise ModelConfigurationError("Gemini credential accessor is required")
        if (
            type(self.timeout_seconds) not in (int, float)
            or not 0 < self.timeout_seconds <= 300
            or type(self.max_retries) is not int
            or not 0 <= self.max_retries <= 10
            or type(self.retry_backoff_seconds) not in (int, float)
            or not 0 <= self.retry_backoff_seconds <= 30
            or type(self.redaction_terms) is not tuple
            or any(not isinstance(term, str) or not term for term in self.redaction_terms)
        ):
            raise ModelConfigurationError("Gemini execution settings are invalid")

    def open(self, audit_sink: ProviderAuditSink) -> AbstractAsyncContextManager[OfficeComposition]:
        if (
            audit_sink is None
            or isinstance(audit_sink, NullProviderAuditSink)
            or not callable(getattr(audit_sink, "record", None))
        ):
            raise ModelConfigurationError("Request audit sink is required")
        return _GeminiScope(self, audit_sink)


class _ScopedGateway:
    def __init__(self, gateway: GeminiInteractionsGateway) -> None:
        self._gateway: GeminiInteractionsGateway | None = gateway
        self._running: asyncio.Task | None = None

    async def generate(self, request: ModelRequest) -> ModelResponse:
        if self._gateway is None or self._running is not None:
            raise ModelConfigurationError("Gemini request scope is unavailable")
        self._running = asyncio.current_task()
        try:
            return await self._gateway.generate(request)
        finally:
            self._running = None

    async def revoke(self) -> None:
        # Revoke first, then drain any child invocation before releasing its lease.
        self._gateway = None
        running = self._running
        if running is not None and running is not asyncio.current_task():
            running.cancel()
            await asyncio.gather(running, return_exceptions=True)
        self._running = None


class _GeminiScope:
    def __init__(self, factory: GeminiRequestExecutionScopeFactory, audit_sink: ProviderAuditSink):
        self._factory = factory
        self._audit_sink: ProviderAuditSink | None = audit_sink
        self._lease: AbstractAsyncContextManager[SecretStr] | None = None
        self._gateway: _ScopedGateway | None = None
        self._entered = False
        self._closed = False

    async def __aenter__(self) -> OfficeComposition:
        if self._entered or self._closed:
            raise ModelConfigurationError("Gemini request scope is one-shot")
        self._entered = True
        credential = None
        key = None
        gateway = None
        try:
            lease = self._factory.credential_accessor.open()
            # A failing __aenter__ owns its own partial acquisition cleanup.
            credential = await lease.__aenter__()
            self._lease = lease
            if not isinstance(credential, SecretStr):
                raise ModelConfigurationError("Gemini credential is invalid")
            key = credential.get_secret_value()
            if not key or key != key.strip() or len(key) > 4096:
                raise ModelConfigurationError("Gemini credential is invalid")
            f = self._factory
            try:
                gateway = GeminiInteractionsGateway(
                    key,
                    model=f.blueprint.logical_model_id,
                    provider_model_name=f.blueprint.provider_model_name,
                    timeout_seconds=f.timeout_seconds,
                    max_retries=f.max_retries,
                    retry_backoff_seconds=f.retry_backoff_seconds,
                    transmission_policy=ProviderTransmissionPolicy(
                        {"gemini": frozenset({DataClassification.PUBLIC})}
                    ),
                    redactor=RegexRedactor(f.redaction_terms),
                    audit_sink=self._audit_sink,
                )
            finally:
                key = None
            self._gateway = _ScopedGateway(gateway)
            return build_office_composition_from_gateway(
                self._gateway, provider="gemini", model_id=f.blueprint.logical_model_id
            )
        except BaseException as exc:
            await self._cleanup(primary=True)
            if isinstance(exc, (asyncio.CancelledError, KeyboardInterrupt, SystemExit)):
                raise
            raise ModelConfigurationError("Gemini request scope could not be opened") from None
        finally:
            credential = None
            key = None
            gateway = None

    async def _cleanup(self, *, primary: bool) -> None:
        self._closed = True
        gateway, self._gateway = self._gateway, None
        lease, self._lease = self._lease, None
        self._audit_sink = None
        # Keep ownership until cleanup finishes even if the scope owner is cancelled.
        cleanup = asyncio.create_task(self._release(gateway, lease))
        cancellation = None
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError as exc:
                cancellation = exc
        failure = cleanup.result()
        if not primary:
            if cancellation is not None:
                raise cancellation
            if failure:
                raise ModelConfigurationError("Gemini request scope cleanup failed") from None

    @staticmethod
    async def _release(gateway, lease) -> bool:
        failure = False
        try:
            if gateway is not None:
                await gateway.revoke()
        except BaseException:
            failure = True
        finally:
            if lease is not None:
                try:
                    # Never expose an application exception or traceback to the secret backend.
                    await lease.__aexit__(None, None, None)
                except BaseException:
                    failure = True
        return failure

    async def __aexit__(self, exc_type, exc, traceback) -> bool:
        if not self._entered or self._closed:
            raise ModelConfigurationError("Gemini request scope is unavailable")
        await self._cleanup(primary=exc_type is not None)
        return False


__all__ = ("GeminiCredentialAccessor", "GeminiRequestExecutionScopeFactory")
