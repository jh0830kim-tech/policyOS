"""Protocols for the CP9 trusted Runtime API application boundary."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_claims import VerifiedAccessTokenClaims
from app.runtime.ports import (
    RuntimeApiActiveTransactionContext,
    RuntimeApiActiveTransactionPersistencePort,
    RuntimeApiQueryProjectionLocator,
    RuntimeRatePolicyProvisionCommand,
    RuntimeRatePolicyProvisionResult,
    RuntimeRatePolicyRevocationCommand,
    RuntimeRatePolicyRevocationResult,
)
from app.services.runtime_api_contracts import (
    BoundedDigest,
    BoundedReference,
    RuntimeApiClockReading,
    RuntimeApiCommandIdentity,
    RuntimeApiDeadlineBudgetRequest,
    RuntimeApiDeadlineBudgetResult,
    RuntimeApiDisconnectObservationRequest,
    RuntimeApiDisconnectObservationResult,
    RuntimeApiDomainOperationResult,
    RuntimeApiIdempotencyCommitFacts,
    RuntimeApiIdempotencyCommitResult,
    RuntimeApiInvocationQuery,
    RuntimeApiInvocationQueryBindingFacts,
    RuntimeApiInvocationQueryFacts,
    RuntimeApiInvocationQueryInput,
    RuntimeApiInvocationQueryIntegrationFacts,
    RuntimeApiOperation,
    RuntimeApiOrganizationSelector,
    RuntimeApiPermission,
    RuntimeApiPermissionFact,
    RuntimeApiPreparationProvenance,
    RuntimeApiRateAdmissionRequest,
    RuntimeApiRateAdmissionResult,
    RuntimeApiReconciliationBindingFacts,
    RuntimeApiReconciliationCommand,
    RuntimeApiReconciliationFacts,
    RuntimeApiReconciliationInput,
    RuntimeApiReconciliationIntegrationFacts,
    RuntimeApiReconciliationResult,
    RuntimeApiSafeResult,
    RuntimeApiStatusProjection,
    RuntimeApiSubmissionBindingFacts,
    RuntimeApiSubmissionCommand,
    RuntimeApiSubmissionFacts,
    RuntimeApiSubmissionInput,
    RuntimeApiSubmissionIntegrationFacts,
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
class RuntimeApiIntegrationFactsProvider(Protocol):
    """Supply immutable expected facts once for one trusted request scope."""

    async def provide_submission(self) -> RuntimeApiSubmissionIntegrationFacts: ...

    async def provide_query(self) -> RuntimeApiInvocationQueryIntegrationFacts: ...

    async def provide_reconciliation(
        self,
    ) -> RuntimeApiReconciliationIntegrationFacts: ...


@runtime_checkable
class RuntimeApiQueryProjectionLocatorProvider(Protocol):
    """Supply one trusted query-only exact locator for one request scope."""

    async def locate_query(self) -> RuntimeApiQueryProjectionLocator: ...


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
class RuntimeApiDomainOperationCallback(Protocol):
    """Execute one validated mutation command and return its sibling outputs once."""

    async def __call__(
        self,
        command: RuntimeApiSubmissionCommand | RuntimeApiReconciliationCommand,
    ) -> RuntimeApiDomainOperationResult: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeApiPreparedSubmission:
    """One inert, server-owned submission candidate for one request."""

    provenance: RuntimeApiPreparationProvenance
    facts: RuntimeApiSubmissionFacts
    domain_callback: RuntimeApiDomainOperationCallback

    def __post_init__(self) -> None:
        if not isinstance(self.provenance, RuntimeApiPreparationProvenance):
            raise TypeError("prepared submission provenance differs")
        if not isinstance(self.facts, RuntimeApiSubmissionFacts):
            raise TypeError("prepared submission facts differ")
        if not isinstance(self.domain_callback, RuntimeApiDomainOperationCallback):
            raise TypeError("prepared submission callback differs")
        if (
            self.provenance.operation is not RuntimeApiOperation.SUBMIT_INVOCATION
            or self.provenance.request_identity != self.facts.command_id
            or self.provenance.canonical_request_digest != self.facts.integration.command_digest
            or self.provenance.correlation_reference != self.facts.correlation_reference
            or (
                self.provenance.tenant_id,
                self.provenance.organization_id,
                self.provenance.classification,
            )
            != (
                self.facts.integration.tenant_id,
                self.facts.integration.organization_id,
                self.facts.integration.classification,
            )
        ):
            raise ValueError("prepared submission provenance binding differs")


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeApiPreparedInvocationQuery:
    """One inert, server-owned exact query candidate for one request."""

    provenance: RuntimeApiPreparationProvenance
    facts: RuntimeApiInvocationQueryFacts

    def __post_init__(self) -> None:
        if not isinstance(self.provenance, RuntimeApiPreparationProvenance):
            raise TypeError("prepared query provenance differs")
        if not isinstance(self.facts, RuntimeApiInvocationQueryFacts):
            raise TypeError("prepared query facts differ")
        if (
            self.provenance.operation is not RuntimeApiOperation.GET_INVOCATION
            or self.provenance.request_identity != self.facts.query_id
            or self.provenance.correlation_reference != self.facts.correlation_reference
            or (
                self.provenance.tenant_id,
                self.provenance.organization_id,
                self.provenance.classification,
            )
            != (
                self.facts.integration.tenant_id,
                self.facts.integration.organization_id,
                self.facts.integration.classification,
            )
        ):
            raise ValueError("prepared query provenance binding differs")


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeApiPreparedReconciliation:
    """One inert, server-owned reconciliation candidate for one request."""

    provenance: RuntimeApiPreparationProvenance
    facts: RuntimeApiReconciliationFacts
    domain_callback: RuntimeApiDomainOperationCallback

    def __post_init__(self) -> None:
        if not isinstance(self.provenance, RuntimeApiPreparationProvenance):
            raise TypeError("prepared reconciliation provenance differs")
        if not isinstance(self.facts, RuntimeApiReconciliationFacts):
            raise TypeError("prepared reconciliation facts differ")
        if not isinstance(self.domain_callback, RuntimeApiDomainOperationCallback):
            raise TypeError("prepared reconciliation callback differs")
        if (
            self.provenance.operation is not RuntimeApiOperation.REQUEST_RECONCILIATION
            or self.provenance.request_identity != self.facts.command_id
            or self.provenance.canonical_request_digest != self.facts.integration.command_digest
            or self.provenance.correlation_reference != self.facts.correlation_reference
            or (
                self.provenance.tenant_id,
                self.provenance.organization_id,
                self.provenance.classification,
            )
            != (
                self.facts.integration.tenant_id,
                self.facts.integration.organization_id,
                self.facts.integration.classification,
            )
        ):
            raise ValueError("prepared reconciliation provenance binding differs")


@runtime_checkable
class RuntimeApiTrustedPreparationSource(Protocol):
    """Select exactly one already-governed candidate for one request scope."""

    async def prepare_submission(
        self,
        claims: VerifiedAccessTokenClaims,
        organization: RuntimeApiOrganizationSelector,
        request: RuntimeApiSubmissionInput,
    ) -> RuntimeApiPreparedSubmission: ...

    async def prepare_query(
        self,
        claims: VerifiedAccessTokenClaims,
        organization: RuntimeApiOrganizationSelector,
        request: RuntimeApiInvocationQueryInput,
    ) -> RuntimeApiPreparedInvocationQuery: ...

    async def prepare_reconciliation(
        self,
        claims: VerifiedAccessTokenClaims,
        organization: RuntimeApiOrganizationSelector,
        request: RuntimeApiReconciliationInput,
    ) -> RuntimeApiPreparedReconciliation: ...


@runtime_checkable
class RuntimeApiPreparationIssuer(Protocol):
    """Assemble one inert package from explicit server-owned inputs."""

    async def issue_submission(
        self,
        provenance: RuntimeApiPreparationProvenance,
        facts: RuntimeApiSubmissionFacts,
        domain_callback: RuntimeApiDomainOperationCallback,
    ) -> RuntimeApiPreparedSubmission: ...

    async def issue_query(
        self,
        provenance: RuntimeApiPreparationProvenance,
        facts: RuntimeApiInvocationQueryFacts,
    ) -> RuntimeApiPreparedInvocationQuery: ...

    async def issue_reconciliation(
        self,
        provenance: RuntimeApiPreparationProvenance,
        facts: RuntimeApiReconciliationFacts,
        domain_callback: RuntimeApiDomainOperationCallback,
    ) -> RuntimeApiPreparedReconciliation: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeApiSubmissionPreparationContext:
    """Explicit server-owned inputs for one submission preparation."""

    provenance: RuntimeApiPreparationProvenance
    clock: RuntimeApiClockReading
    facts: RuntimeApiSubmissionFacts
    domain_callback: RuntimeApiDomainOperationCallback

    def __post_init__(self) -> None:
        RuntimeApiPreparedSubmission(
            provenance=self.provenance,
            facts=self.facts,
            domain_callback=self.domain_callback,
        )
        if (
            self.clock.clock_reference != self.provenance.clock_reference
            or self.clock.observed_at != self.provenance.evaluated_at
        ):
            raise ValueError("submission preparation clock differs")


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeApiInvocationQueryPreparationContext:
    """Explicit server-owned inputs for one read-only query preparation."""

    provenance: RuntimeApiPreparationProvenance
    clock: RuntimeApiClockReading
    facts: RuntimeApiInvocationQueryFacts

    def __post_init__(self) -> None:
        RuntimeApiPreparedInvocationQuery(provenance=self.provenance, facts=self.facts)
        if (
            self.clock.clock_reference != self.provenance.clock_reference
            or self.clock.observed_at != self.provenance.evaluated_at
        ):
            raise ValueError("query preparation clock differs")


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeApiReconciliationPreparationContext:
    """Explicit server-owned inputs for one reconciliation preparation."""

    provenance: RuntimeApiPreparationProvenance
    clock: RuntimeApiClockReading
    facts: RuntimeApiReconciliationFacts
    domain_callback: RuntimeApiDomainOperationCallback

    def __post_init__(self) -> None:
        RuntimeApiPreparedReconciliation(
            provenance=self.provenance,
            facts=self.facts,
            domain_callback=self.domain_callback,
        )
        if (
            self.clock.clock_reference != self.provenance.clock_reference
            or self.clock.observed_at != self.provenance.evaluated_at
        ):
            raise ValueError("reconciliation preparation clock differs")


@runtime_checkable
class RuntimeApiPreparationProducer(Protocol):
    """Validate explicit trusted inputs and issue one inert package."""

    async def produce_submission(
        self,
        claims: VerifiedAccessTokenClaims,
        organization: RuntimeApiOrganizationSelector,
        request: RuntimeApiSubmissionInput,
        context: RuntimeApiSubmissionPreparationContext,
    ) -> RuntimeApiPreparedSubmission: ...

    async def produce_query(
        self,
        claims: VerifiedAccessTokenClaims,
        organization: RuntimeApiOrganizationSelector,
        request: RuntimeApiInvocationQueryInput,
        context: RuntimeApiInvocationQueryPreparationContext,
    ) -> RuntimeApiPreparedInvocationQuery: ...

    async def produce_reconciliation(
        self,
        claims: VerifiedAccessTokenClaims,
        organization: RuntimeApiOrganizationSelector,
        request: RuntimeApiReconciliationInput,
        context: RuntimeApiReconciliationPreparationContext,
    ) -> RuntimeApiPreparedReconciliation: ...


@runtime_checkable
class RuntimeApiDomainOperationCapability(Protocol):
    """Supply one operation-bound callback for the current request only."""

    async def submission_callback(
        self,
        provenance: RuntimeApiPreparationProvenance,
        facts: RuntimeApiSubmissionFacts,
    ) -> RuntimeApiDomainOperationCallback: ...

    async def reconciliation_callback(
        self,
        provenance: RuntimeApiPreparationProvenance,
        facts: RuntimeApiReconciliationFacts,
    ) -> RuntimeApiDomainOperationCallback: ...


@runtime_checkable
class RuntimeClockPort(Protocol):
    """Read one explicitly identified trusted clock for the request scope."""

    async def read(self, clock_reference: BoundedReference) -> RuntimeApiClockReading: ...


@runtime_checkable
class RuntimeApiRateAdmissionCapability(Protocol):
    async def admit(
        self, request: RuntimeApiRateAdmissionRequest
    ) -> RuntimeApiRateAdmissionResult: ...


@runtime_checkable
class RuntimeRatePolicyManagementCapability(Protocol):
    """Provision or revoke one exact policy revision outside public routes."""

    async def provision(
        self, command: RuntimeRatePolicyProvisionCommand
    ) -> RuntimeRatePolicyProvisionResult: ...

    async def revoke(
        self, command: RuntimeRatePolicyRevocationCommand
    ) -> RuntimeRatePolicyRevocationResult: ...


@runtime_checkable
class RuntimeApiDeadlineBudgetCapability(Protocol):
    async def evaluate(
        self, request: RuntimeApiDeadlineBudgetRequest
    ) -> RuntimeApiDeadlineBudgetResult: ...


@runtime_checkable
class RuntimeApiDisconnectObservationCapability(Protocol):
    async def observe(
        self, request: RuntimeApiDisconnectObservationRequest
    ) -> RuntimeApiDisconnectObservationResult: ...


@runtime_checkable
class RuntimeApiPreparedApplicationEntry(Protocol):
    """Expose one trusted prepared application boundary to thin routes."""

    async def submit_invocation(
        self,
        request: RuntimeApiSubmissionInput,
        claims: VerifiedAccessTokenClaims,
        organization: RuntimeApiOrganizationSelector,
    ) -> RuntimeApiSubmissionResult: ...

    async def get_invocation(
        self,
        request: RuntimeApiInvocationQueryInput,
        claims: VerifiedAccessTokenClaims,
        organization: RuntimeApiOrganizationSelector,
    ) -> RuntimeApiStatusProjection: ...

    async def request_reconciliation(
        self,
        request: RuntimeApiReconciliationInput,
        claims: VerifiedAccessTokenClaims,
        organization: RuntimeApiOrganizationSelector,
    ) -> RuntimeApiReconciliationResult: ...


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
    "RuntimeApiDomainOperationCapability",
    "RuntimeApiDomainOperationCallback",
    "RuntimeApiDeadlineBudgetCapability",
    "RuntimeApiDisconnectObservationCapability",
    "RuntimeApiIdempotencyTransactionPort",
    "RuntimeApiIntegrationFactsProvider",
    "RuntimeApiInvocationQueryPreparationContext",
    "RuntimeApiLocalMutation",
    "RuntimeApiLocalOperationPort",
    "RuntimeApiOrchestrationFactBinder",
    "RuntimeApiPermissionFactResolver",
    "RuntimeApiPreparedApplicationEntry",
    "RuntimeApiPreparedInvocationQuery",
    "RuntimeApiPreparedReconciliation",
    "RuntimeApiPreparedSubmission",
    "RuntimeApiPreparationIssuer",
    "RuntimeApiPreparationProducer",
    "RuntimeApiPersistedOrchestrationFactBinder",
    "RuntimeApiQueryProjectionLocatorProvider",
    "RuntimeApiRateAdmissionCapability",
    "RuntimeRatePolicyManagementCapability",
    "RuntimeApiReconciliationPreparationContext",
    "RuntimeApiSubmissionPreparationContext",
    "RuntimeApiTrustedPreparationSource",
    "RuntimeApiTrustedContextResolver",
    "RuntimeClockPort",
)
