"""Production composition for the trusted CP9 Runtime application boundary."""

from __future__ import annotations

import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass
from enum import Enum, auto
from types import TracebackType
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.auth_claims import VerifiedAccessTokenClaims
from app.runtime.persistence import (
    SQLAlchemyRuntimeApiActiveTransactionPersistenceFactory,
    SQLAlchemyRuntimeRateAdmissionRepository,
)
from app.runtime.ports import RuntimeRateAdmissionDisposition
from app.services.runtime_api_contracts import (
    RuntimeApiContractConflict,
    RuntimeApiDeadlineDisposition,
    RuntimeApiDisconnectDisposition,
    RuntimeApiRateAdmissionRequest,
    RuntimeApiRateAdmissionResult,
)
from app.services.runtime_api_facade import SQLAlchemyRuntimeApiApplicationFacade
from app.services.runtime_api_integration import (
    RuntimeApiActiveTransactionLocalOperation,
    RuntimeApiExactOrchestrationFactBinder,
)
from app.services.runtime_api_protocols import (
    RuntimeApiDeadlineBudgetCapability,
    RuntimeApiDeadlineBudgetCapabilityFactory,
    RuntimeApiDisconnectObservationCapability,
    RuntimeApiDisconnectObservationCapabilityFactory,
    RuntimeApiDomainOperationCapabilityFactory,
    RuntimeApiPreparationContextProvider,
    RuntimeApiPreparationContextUpstream,
    RuntimeApiPreparationContextUpstreamFactory,
    RuntimeApiPreparationIssuer,
    RuntimeApiPreparationProducer,
    RuntimeApiPreparedApplicationEntry,
    RuntimeApiPreparedInvocationQuery,
    RuntimeApiPreparedReconciliation,
    RuntimeApiPreparedSubmission,
    RuntimeApiProductionDependencyBundle,
    RuntimeApiRateAdmissionCapability,
    RuntimeApiRateAdmissionCapabilityFactory,
    RuntimeApiRequestCapabilityScope,
    RuntimeApiRequestDependencies,
    RuntimeApiTrustedPreparationSource,
    RuntimeClockFactory,
)
from app.services.runtime_api_validation import (
    validate_runtime_api_clock_binding,
    validate_runtime_api_operational_preflight,
    validate_runtime_api_preparation_provenance,
)


class RuntimeApiProductionError(RuntimeError):
    """A bounded production composition failure."""


class RuntimeApiDependencyUnavailable(RuntimeApiProductionError):
    """A required request-local capability is unavailable."""


class RuntimeApiRateLimited(RuntimeApiProductionError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("runtime request rate limited")
        self.retry_after_seconds = retry_after_seconds


class _SourceState(Enum):
    AVAILABLE = auto()
    INSPECTED = auto()
    CONSUMED = auto()
    REJECTED = auto()


class RuntimeApiProductionPreparationContextProvider:
    """Delegate exactly once to the authoritative request-local upstream."""

    def __init__(self, upstream: RuntimeApiPreparationContextUpstream) -> None:
        self._upstream = upstream
        self._used = False

    def _enter(self) -> None:
        if self._used:
            raise RuntimeApiContractConflict("preparation context provider is one-shot")
        self._used = True

    async def provide_submission(self, claims, organization, request):
        self._enter()
        return await self._upstream.prepare_submission(claims, organization, request)

    async def provide_query(self, claims, organization, request):
        self._enter()
        return await self._upstream.prepare_query(claims, organization, request)

    async def provide_reconciliation(self, claims, organization, request):
        self._enter()
        return await self._upstream.prepare_reconciliation(claims, organization, request)


class RuntimeApiProductionPreparationIssuer:
    async def issue_submission(self, provenance, preflight, facts, domain_callback):
        return RuntimeApiPreparedSubmission(
            provenance=provenance,
            preflight=preflight,
            facts=facts,
            domain_callback=domain_callback,
        )

    async def issue_query(self, provenance, preflight, facts):
        return RuntimeApiPreparedInvocationQuery(
            provenance=provenance,
            preflight=preflight,
            facts=facts,
        )

    async def issue_reconciliation(self, provenance, preflight, facts, domain_callback):
        return RuntimeApiPreparedReconciliation(
            provenance=provenance,
            preflight=preflight,
            facts=facts,
            domain_callback=domain_callback,
        )


class RuntimeApiProductionPreparationProducer:
    def __init__(self, issuer: RuntimeApiPreparationIssuer) -> None:
        self._issuer = issuer

    @staticmethod
    def _validate(claims, organization, request, context) -> None:
        provenance = validate_runtime_api_preparation_provenance(
            context.provenance,
            expected=context.provenance,
        )
        validate_runtime_api_clock_binding(context.clock, provenance=provenance)
        validate_runtime_api_operational_preflight(context.preflight, provenance=provenance)
        if organization.organization_id != provenance.organization_id:
            raise RuntimeApiContractConflict("prepared organization differs")
        if provenance.request_identity not in (
            getattr(context.facts, "command_id", None),
            getattr(context.facts, "query_id", None),
        ):
            raise RuntimeApiContractConflict("prepared request identity differs")
        if provenance.correlation_reference != context.facts.correlation_reference:
            raise RuntimeApiContractConflict("prepared correlation differs")
        if not isinstance(claims, VerifiedAccessTokenClaims):
            raise RuntimeApiContractConflict("verified claims differ")
        if request is None:
            raise RuntimeApiContractConflict("runtime request differs")

    async def produce_submission(self, claims, organization, request, context):
        self._validate(claims, organization, request, context)
        if context.facts.integration.action_reference != request.action_reference:
            raise RuntimeApiContractConflict("submission action differs")
        return await self._issuer.issue_submission(
            context.provenance,
            context.preflight,
            context.facts,
            context.domain_callback,
        )

    async def produce_query(self, claims, organization, request, context):
        self._validate(claims, organization, request, context)
        if context.facts.integration.invocation_reference != request.invocation_reference:
            raise RuntimeApiContractConflict("query invocation differs")
        return await self._issuer.issue_query(
            context.provenance,
            context.preflight,
            context.facts,
        )

    async def produce_reconciliation(self, claims, organization, request, context):
        self._validate(claims, organization, request, context)
        if (
            context.facts.integration.invocation_reference,
            context.facts.integration.reconciliation_reference,
        ) != (request.invocation_reference, request.reconciliation_reference):
            raise RuntimeApiContractConflict("reconciliation identity differs")
        return await self._issuer.issue_reconciliation(
            context.provenance,
            context.preflight,
            context.facts,
            context.domain_callback,
        )


class RuntimeApiProductionPreparationSource:
    """Keep one inert candidate inspectable until exactly one terminal transition."""

    def __init__(
        self,
        provider: RuntimeApiPreparationContextProvider,
        producer: RuntimeApiPreparationProducer,
    ) -> None:
        self._provider = provider
        self._producer = producer
        self._state = _SourceState.AVAILABLE
        self._candidate = None

    def _inspect(self, candidate):
        if self._state is not _SourceState.AVAILABLE:
            raise RuntimeApiContractConflict("preparation source is not available")
        self._state = _SourceState.INSPECTED
        self._candidate = candidate
        return candidate

    def _finish(self, candidate, state: _SourceState):
        if self._state is not _SourceState.INSPECTED or candidate is not self._candidate:
            raise RuntimeApiContractConflict("prepared candidate identity differs")
        self._state = state
        return candidate

    async def inspect_submission(self, claims, organization, request):
        context = await self._provider.provide_submission(claims, organization, request)
        return self._inspect(
            await self._producer.produce_submission(claims, organization, request, context)
        )

    async def inspect_query(self, claims, organization, request):
        context = await self._provider.provide_query(claims, organization, request)
        return self._inspect(
            await self._producer.produce_query(claims, organization, request, context)
        )

    async def inspect_reconciliation(self, claims, organization, request):
        context = await self._provider.provide_reconciliation(claims, organization, request)
        return self._inspect(
            await self._producer.produce_reconciliation(claims, organization, request, context)
        )

    async def consume_submission(self, candidate):
        return self._finish(candidate, _SourceState.CONSUMED)

    async def consume_query(self, candidate):
        return self._finish(candidate, _SourceState.CONSUMED)

    async def consume_reconciliation(self, candidate):
        return self._finish(candidate, _SourceState.CONSUMED)

    async def reject_submission(self, candidate):
        self._finish(candidate, _SourceState.REJECTED)

    async def reject_query(self, candidate):
        self._finish(candidate, _SourceState.REJECTED)

    async def reject_reconciliation(self, candidate):
        self._finish(candidate, _SourceState.REJECTED)


class SQLAlchemyRuntimeApiRateAdmissionCapability:
    """Commit rate admission in a transaction independent of the facade session."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def admit(self, request: RuntimeApiRateAdmissionRequest) -> RuntimeApiRateAdmissionResult:
        async with self._session_factory() as session, session.begin():
            persistence = await SQLAlchemyRuntimeRateAdmissionRepository(session).admit(
                request.decision
            )
        return RuntimeApiRateAdmissionResult(request=request, persistence=persistence)


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeApiProductionEntry:
    source: RuntimeApiTrustedPreparationSource
    rate_admission: RuntimeApiRateAdmissionCapability
    deadline_budget: RuntimeApiDeadlineBudgetCapability
    disconnect_observation: RuntimeApiDisconnectObservationCapability
    session: AsyncSession
    required_audience: str

    async def _preflight(self, candidate, reject) -> None:
        rate = await self.rate_admission.admit(candidate.preflight.rate_admission)
        if rate.persistence.decision.disposition is RuntimeRateAdmissionDisposition.DENIED:
            await reject(candidate)
            retry = rate.persistence.decision.retry_after_seconds
            if retry is None:
                raise RuntimeApiDependencyUnavailable("rate decision is incomplete")
            raise RuntimeApiRateLimited(retry)
        deadline = await self.deadline_budget.evaluate(candidate.preflight.deadline_budget)
        if deadline.disposition is RuntimeApiDeadlineDisposition.EXPIRED:
            await reject(candidate)
            raise RuntimeApiDependencyUnavailable("runtime request unavailable")
        disconnect = await self.disconnect_observation.observe(
            candidate.preflight.disconnect_observation
        )
        if disconnect.disposition is RuntimeApiDisconnectDisposition.DISCONNECTED:
            await reject(candidate)
            raise RuntimeApiDependencyUnavailable("runtime request unavailable")

    def _facade(self, callback):
        persistence_factory = SQLAlchemyRuntimeApiActiveTransactionPersistenceFactory()
        return SQLAlchemyRuntimeApiApplicationFacade(
            self.session,
            required_audience=self.required_audience,
            binder_factory=RuntimeApiExactOrchestrationFactBinder,
            local_operation_factory=lambda session: RuntimeApiActiveTransactionLocalOperation(
                session,
                persistence_factory=persistence_factory,
                state_reader_factory=persistence_factory,
                logical_result_reader_factory=persistence_factory,
                domain_callback=callback,
            ),
        )

    async def submit_invocation(self, request, claims, organization):
        candidate = await self.source.inspect_submission(claims, organization, request)
        await self._preflight(candidate, self.source.reject_submission)
        candidate = await self.source.consume_submission(candidate)
        return await self._facade(candidate.domain_callback).submit_invocation(
            request, claims, organization, candidate.facts
        )

    async def get_invocation(self, request, claims, organization):
        candidate = await self.source.inspect_query(claims, organization, request)
        await self._preflight(candidate, self.source.reject_query)
        candidate = await self.source.consume_query(candidate)
        return await self._facade(_QueryCallback()).get_invocation(
            request, claims, organization, candidate.facts
        )

    async def request_reconciliation(self, request, claims, organization):
        candidate = await self.source.inspect_reconciliation(claims, organization, request)
        await self._preflight(candidate, self.source.reject_reconciliation)
        candidate = await self.source.consume_reconciliation(candidate)
        return await self._facade(candidate.domain_callback).request_reconciliation(
            request, claims, organization, candidate.facts
        )


class _QueryCallback:
    async def __call__(self, command):
        raise RuntimeApiContractConflict("read-only query cannot invoke a domain callback")


class RuntimeApiRequestScopeCoordinator:
    """Enter six managed resources in order and release them in exact reverse order."""

    def __init__(self, bundle: RuntimeApiProductionDependencyBundle, signal) -> None:
        self._factory = bundle.request_capability_scope_factory
        self._signal = signal
        self._scope: RuntimeApiRequestCapabilityScope | None = None

    async def __aenter__(self) -> RuntimeApiRequestDependencies:
        self._scope = self._factory(self._signal)
        return await self._scope.__aenter__()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        if self._scope is None:
            return False
        return await self._scope.__aexit__(exc_type, exc, traceback)


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeApiProductionRequestScopeFactory:
    """Construct one fresh six-resource request scope from immutable factories."""

    domain_operation_factory: RuntimeApiDomainOperationCapabilityFactory
    clock_factory: RuntimeClockFactory
    rate_admission_factory: RuntimeApiRateAdmissionCapabilityFactory
    deadline_budget_factory: RuntimeApiDeadlineBudgetCapabilityFactory
    disconnect_observation_factory: RuntimeApiDisconnectObservationCapabilityFactory
    preparation_upstream_factory: RuntimeApiPreparationContextUpstreamFactory

    def __post_init__(self) -> None:
        expected = (
            (self.domain_operation_factory, RuntimeApiDomainOperationCapabilityFactory),
            (self.clock_factory, RuntimeClockFactory),
            (self.rate_admission_factory, RuntimeApiRateAdmissionCapabilityFactory),
            (self.deadline_budget_factory, RuntimeApiDeadlineBudgetCapabilityFactory),
            (
                self.disconnect_observation_factory,
                RuntimeApiDisconnectObservationCapabilityFactory,
            ),
            (
                self.preparation_upstream_factory,
                RuntimeApiPreparationContextUpstreamFactory,
            ),
        )
        if any(not isinstance(value, contract) for value, contract in expected):
            raise TypeError("Runtime request capability factory graph differs")

    def __call__(self, signal):
        return _RuntimeApiProductionRequestScope(self, signal)


@dataclass(slots=True)
class _CapabilityLease:
    active: bool = True


class _GuardedCapability:
    def __init__(self, target, lease: _CapabilityLease) -> None:
        self._target = target
        self._lease = lease

    def __getattr__(self, name):
        member = getattr(self._target, name)

        async def guarded(*args, **kwargs):
            if not self._lease.active:
                raise RuntimeApiDependencyUnavailable(
                    "request capability is outside its managed lifetime"
                )
            return await member(*args, **kwargs)

        return guarded

    async def submission_callback(self, provenance, facts):
        return await self.__getattr__("submission_callback")(provenance, facts)

    async def reconciliation_callback(self, provenance, facts):
        return await self.__getattr__("reconciliation_callback")(provenance, facts)

    async def read(self, clock_reference):
        return await self.__getattr__("read")(clock_reference)

    async def admit(self, request):
        return await self.__getattr__("admit")(request)

    async def evaluate(self, request):
        return await self.__getattr__("evaluate")(request)

    async def observe(self, request):
        return await self.__getattr__("observe")(request)

    async def prepare_submission(self, claims, organization, request):
        return await self.__getattr__("prepare_submission")(claims, organization, request)

    async def prepare_query(self, claims, organization, request):
        return await self.__getattr__("prepare_query")(claims, organization, request)

    async def prepare_reconciliation(self, claims, organization, request):
        return await self.__getattr__("prepare_reconciliation")(claims, organization, request)


class _RuntimeApiProductionRequestScope:
    def __init__(self, factories: RuntimeApiProductionRequestScopeFactory, signal) -> None:
        self._factories = factories
        self._signal = signal
        self._stack: AsyncExitStack | None = None
        self._lease = _CapabilityLease()
        self._entered = False

    async def __aenter__(self) -> RuntimeApiRequestDependencies:
        if self._entered:
            raise RuntimeApiDependencyUnavailable("request capability scope is one-shot")
        self._entered = True
        stack = AsyncExitStack()
        self._stack = stack
        await stack.__aenter__()
        try:
            domain_operation_value = await stack.enter_async_context(
                self._factories.domain_operation_factory()
            )
            domain_operation = _GuardedCapability(domain_operation_value, self._lease)
            clock_value = await stack.enter_async_context(self._factories.clock_factory())
            clock = _GuardedCapability(clock_value, self._lease)
            rate_admission_value = await stack.enter_async_context(
                self._factories.rate_admission_factory()
            )
            rate_admission = _GuardedCapability(rate_admission_value, self._lease)
            deadline_budget_value = await stack.enter_async_context(
                self._factories.deadline_budget_factory()
            )
            deadline_budget = _GuardedCapability(deadline_budget_value, self._lease)
            disconnect_observation_value = await stack.enter_async_context(
                self._factories.disconnect_observation_factory(self._signal)
            )
            disconnect_observation = _GuardedCapability(disconnect_observation_value, self._lease)
            preparation_upstream_value = await stack.enter_async_context(
                self._factories.preparation_upstream_factory(domain_operation, clock)
            )
            preparation_upstream = _GuardedCapability(preparation_upstream_value, self._lease)
            return RuntimeApiRequestDependencies(
                domain_operation=domain_operation,
                clock=clock,
                rate_admission=rate_admission,
                deadline_budget=deadline_budget,
                disconnect_observation=disconnect_observation,
                preparation_upstream=preparation_upstream,
            )
        except BaseException:
            self._lease.active = False
            await stack.__aexit__(*sys.exc_info())
            raise

    async def __aexit__(self, exc_type, exc, traceback) -> Literal[False]:
        if self._stack is None:
            return False
        self._lease.active = False
        try:
            await self._stack.__aexit__(exc_type, exc, traceback)
        finally:
            self._stack = None
        return False


def build_runtime_api_entry(
    dependencies: RuntimeApiRequestDependencies,
    *,
    session: AsyncSession,
    required_audience: str,
) -> RuntimeApiPreparedApplicationEntry:
    provider = RuntimeApiProductionPreparationContextProvider(dependencies.preparation_upstream)
    producer = RuntimeApiProductionPreparationProducer(RuntimeApiProductionPreparationIssuer())
    source = RuntimeApiProductionPreparationSource(provider, producer)
    return RuntimeApiProductionEntry(
        source=source,
        rate_admission=dependencies.rate_admission,
        deadline_budget=dependencies.deadline_budget,
        disconnect_observation=dependencies.disconnect_observation,
        session=session,
        required_audience=required_audience,
    )


__all__ = (
    "RuntimeApiDependencyUnavailable",
    "RuntimeApiProductionEntry",
    "RuntimeApiProductionError",
    "RuntimeApiProductionPreparationContextProvider",
    "RuntimeApiProductionPreparationIssuer",
    "RuntimeApiProductionPreparationProducer",
    "RuntimeApiProductionPreparationSource",
    "RuntimeApiProductionRequestScopeFactory",
    "RuntimeApiRateLimited",
    "RuntimeApiRequestScopeCoordinator",
    "SQLAlchemyRuntimeApiRateAdmissionCapability",
    "build_runtime_api_entry",
)
