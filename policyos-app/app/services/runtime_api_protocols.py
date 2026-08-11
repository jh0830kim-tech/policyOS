"""Protocols for the CP9 trusted Runtime API application boundary."""

from typing import Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_claims import VerifiedAccessTokenClaims
from app.runtime.ports import (
    RuntimeApiActiveTransactionContext,
    RuntimeApiActiveTransactionPersistencePort,
)
from app.services.runtime_api_contracts import (
    BoundedDigest,
    RuntimeApiCommandIdentity,
    RuntimeApiIdempotencyCommitFacts,
    RuntimeApiIdempotencyCommitResult,
    RuntimeApiInvocationQuery,
    RuntimeApiInvocationQueryBindingFacts,
    RuntimeApiInvocationQueryFacts,
    RuntimeApiInvocationQueryInput,
    RuntimeApiOrganizationSelector,
    RuntimeApiPermission,
    RuntimeApiPermissionFact,
    RuntimeApiReconciliationBindingFacts,
    RuntimeApiReconciliationCommand,
    RuntimeApiReconciliationFacts,
    RuntimeApiReconciliationInput,
    RuntimeApiReconciliationResult,
    RuntimeApiSafeResult,
    RuntimeApiStatusProjection,
    RuntimeApiSubmissionBindingFacts,
    RuntimeApiSubmissionCommand,
    RuntimeApiSubmissionFacts,
    RuntimeApiSubmissionInput,
    RuntimeApiSubmissionResult,
    RuntimeApiTrustedPrincipal,
    RuntimeApiTrustedScope,
)


@runtime_checkable
class RuntimeApiApplicationFacade(Protocol):
    async def submit_invocation(
        self,
        request: RuntimeApiSubmissionInput,
        claims: VerifiedAccessTokenClaims,
        organization: RuntimeApiOrganizationSelector,
        facts: RuntimeApiSubmissionFacts,
    ) -> RuntimeApiSubmissionResult: ...

    async def get_invocation(
        self,
        request: RuntimeApiInvocationQueryInput,
        claims: VerifiedAccessTokenClaims,
        organization: RuntimeApiOrganizationSelector,
        facts: RuntimeApiInvocationQueryFacts,
    ) -> RuntimeApiStatusProjection: ...

    async def request_reconciliation(
        self,
        request: RuntimeApiReconciliationInput,
        claims: VerifiedAccessTokenClaims,
        organization: RuntimeApiOrganizationSelector,
        facts: RuntimeApiReconciliationFacts,
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
class RuntimeApiOrchestrationFactBinder(Protocol):
    async def bind_submission(
        self,
        principal: RuntimeApiTrustedPrincipal,
        scope: RuntimeApiTrustedScope,
        permission: RuntimeApiPermissionFact,
        request: RuntimeApiSubmissionInput,
        facts: RuntimeApiSubmissionFacts,
        command_digest: BoundedDigest,
    ) -> RuntimeApiSubmissionCommand: ...

    async def bind_query(
        self,
        principal: RuntimeApiTrustedPrincipal,
        scope: RuntimeApiTrustedScope,
        permission: RuntimeApiPermissionFact,
        request: RuntimeApiInvocationQueryInput,
        facts: RuntimeApiInvocationQueryFacts,
    ) -> RuntimeApiInvocationQuery: ...

    async def bind_reconciliation(
        self,
        principal: RuntimeApiTrustedPrincipal,
        scope: RuntimeApiTrustedScope,
        permission: RuntimeApiPermissionFact,
        request: RuntimeApiReconciliationInput,
        facts: RuntimeApiReconciliationFacts,
        command_digest: BoundedDigest,
    ) -> RuntimeApiReconciliationCommand: ...


@runtime_checkable
class RuntimeApiPersistedOrchestrationFactBinder(Protocol):
    async def bind_submission_facts(
        self, facts: RuntimeApiSubmissionBindingFacts
    ) -> RuntimeApiSubmissionBindingFacts: ...

    async def bind_query_facts(
        self, facts: RuntimeApiInvocationQueryBindingFacts
    ) -> RuntimeApiInvocationQueryBindingFacts: ...

    async def bind_reconciliation_facts(
        self, facts: RuntimeApiReconciliationBindingFacts
    ) -> RuntimeApiReconciliationBindingFacts: ...


@runtime_checkable
class RuntimeApiLocalOperationPort(Protocol):
    async def submit_invocation(
        self, command: RuntimeApiSubmissionCommand
    ) -> RuntimeApiSafeResult: ...

    async def get_invocation(
        self, query: RuntimeApiInvocationQuery
    ) -> RuntimeApiStatusProjection: ...

    async def request_reconciliation(
        self, command: RuntimeApiReconciliationCommand
    ) -> RuntimeApiSafeResult: ...


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


@runtime_checkable
class RuntimeApiActiveTransactionPersistenceFactory(Protocol):
    """Create one one-shot capability inside the facade-owned transaction."""

    def __call__(
        self,
        session: AsyncSession,
        context: RuntimeApiActiveTransactionContext,
    ) -> RuntimeApiActiveTransactionPersistencePort: ...


__all__ = (
    "RuntimeApiApplicationFacade",
    "RuntimeApiActiveTransactionPersistenceFactory",
    "RuntimeApiIdempotencyTransactionPort",
    "RuntimeApiLocalMutation",
    "RuntimeApiLocalOperationPort",
    "RuntimeApiOrchestrationFactBinder",
    "RuntimeApiPermissionFactResolver",
    "RuntimeApiPersistedOrchestrationFactBinder",
    "RuntimeApiTrustedContextResolver",
)
