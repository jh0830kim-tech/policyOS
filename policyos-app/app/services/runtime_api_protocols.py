"""Protocols for the CP9 trusted Runtime API application boundary."""

from typing import Protocol, runtime_checkable

from app.services.runtime_api_contracts import (
    RuntimeApiCommandIdentity,
    RuntimeApiIdempotencyCommitFacts,
    RuntimeApiIdempotencyCommitResult,
    RuntimeApiInvocationQuery,
    RuntimeApiPermission,
    RuntimeApiPermissionFact,
    RuntimeApiReconciliationCommand,
    RuntimeApiReconciliationResult,
    RuntimeApiSafeResult,
    RuntimeApiStatusProjection,
    RuntimeApiSubmissionCommand,
    RuntimeApiSubmissionResult,
    RuntimeApiTrustedPrincipal,
    RuntimeApiTrustedScope,
)


@runtime_checkable
class RuntimeApiApplicationFacade(Protocol):
    async def submit_invocation(
        self, command: RuntimeApiSubmissionCommand
    ) -> RuntimeApiSubmissionResult: ...

    async def get_invocation(
        self, query: RuntimeApiInvocationQuery
    ) -> RuntimeApiStatusProjection: ...

    async def request_reconciliation(
        self, command: RuntimeApiReconciliationCommand
    ) -> RuntimeApiReconciliationResult: ...


@runtime_checkable
class RuntimeApiTrustedContextResolver(Protocol):
    async def resolve_principal(self) -> RuntimeApiTrustedPrincipal: ...

    async def resolve_scope(
        self, principal: RuntimeApiTrustedPrincipal
    ) -> RuntimeApiTrustedScope: ...


@runtime_checkable
class RuntimeApiPermissionFactResolver(Protocol):
    async def resolve_permission_fact(
        self,
        principal: RuntimeApiTrustedPrincipal,
        scope: RuntimeApiTrustedScope,
        permission: RuntimeApiPermission,
    ) -> RuntimeApiPermissionFact: ...


@runtime_checkable
class RuntimeApiLocalMutation(Protocol):
    async def __call__(self) -> RuntimeApiSafeResult: ...


@runtime_checkable
class RuntimeApiIdempotencyTransactionPort(Protocol):
    async def commit(
        self,
        identity: RuntimeApiCommandIdentity,
        facts: RuntimeApiIdempotencyCommitFacts,
        mutation: RuntimeApiLocalMutation,
    ) -> RuntimeApiIdempotencyCommitResult: ...


__all__ = (
    "RuntimeApiApplicationFacade",
    "RuntimeApiIdempotencyTransactionPort",
    "RuntimeApiLocalMutation",
    "RuntimeApiPermissionFactResolver",
    "RuntimeApiTrustedContextResolver",
)
